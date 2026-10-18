import { useEffect, useRef, useState } from "react";
import { Engine } from "./engine";
import {
  CausalGraph,
  DistributionChart,
  Histogram,
  Icon,
  JsonDetails,
  Mark,
  fmt,
  label,
  pretty,
} from "./components";
import type { Graph, Model, Progress, Query, Rank, Session } from "./types";

const worlds = [
  {
    id: "equivalence",
    number: "01",
    name: "Same observations, different causes",
    short: "The equivalence puzzle",
    description:
      "Three explanations. One observational distribution. Which experiment tells them apart?",
    tag: "START HERE",
  },
  {
    id: "collider",
    number: "02",
    name: "Collider & selection effects",
    short: "When conditioning connects",
    description:
      "Independent causes can become associated when you condition on their shared outcome.",
    tag: "SELECTION",
  },
  {
    id: "confounding",
    number: "03",
    name: "Observed confounding",
    short: "The confounding reversal",
    description:
      "An observed common cause can reverse the sign of a naive association.",
    tag: "ADJUSTMENT",
  },
  {
    id: "hidden",
    number: "04",
    name: "Hidden-confounder failure",
    short: "A missing piece of the world",
    description: "See what happens when causal sufficiency does not hold.",
    tag: "LIMITS",
  },
  {
    id: "random",
    number: "05",
    name: "Seeded sparse system",
    short: "An unexplored system",
    description:
      "A reproducible sparse system with randomized variable labels.",
    tag: "EXPLORE",
  },
];
const emptyGraph: Graph = { nodes: [], directed: [], undirected: [] };
type Section = "structure" | "experiment" | "query" | "data";
const STORAGE = "meridian.experiment.v1";
const numberInput = (s: string, fallback: number) =>
  Number.isFinite(Number(s)) ? Number(s) : fallback;
const download = (name: string, value: unknown) => {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};
const candidateGraph = (s: Session | null): Graph | undefined =>
  s?.selected === "custom"
    ? s.custom_model
      ? modelGraph(s.custom_model)
      : undefined
    : s?.selected === "notears"
      ? s.notears?.graph
      : s?.candidates?.find((c) => c.id === s.selected)?.graph ||
        s?.candidates?.[0]?.graph;
const modelGraph = (m: Model): Graph => ({
  nodes: m.nodes,
  directed: m.B.flatMap((r, i) =>
    r.flatMap((v, j) =>
      v !== 0 ? [[m.nodes[j], m.nodes[i]] as [string, string]] : [],
    ),
  ),
  undirected: [],
});
const chosenModel = (s: Session | null): Model | undefined =>
  s?.selected === "custom"
    ? s.custom_model
    : s?.selected === "notears"
      ? (s.notears?.model as Model | undefined)
      : s?.candidates?.find((c) => c.id === s.selected)?.model ||
        s?.candidates?.[0]?.model;

export default function App() {
  const engine = useRef<Engine | null>(null);
  const [session, setSession] = useState<Session | null>(null),
    [busy, setBusy] = useState("Starting Python"),
    [progress, setProgress] = useState<Progress>({
      stage: "boot",
      message: "Preparing your local laboratory",
    }),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [world, setWorld] = useState("equivalence"),
    [seed, setSeed] = useState(7),
    [samples, setSamples] = useState(800),
    [alpha, setAlpha] = useState(0.01),
    [depth, setDepth] = useState(3),
    [lambda, setLambda] = useState(0.1),
    [threshold, setThreshold] = useState(0.2),
    [standardize, setStandardize] = useState(true);
  const [view, setView] = useState<"pc" | "notears" | "candidate" | "truth">(
      "pc",
    ),
    [selected, setSelected] = useState("Y"),
    [selectionType, setSelectionType] = useState<"node" | "edge">("node"),
    [section, setSection] = useState<Section>("structure");
  const [query, setQuery] = useState<Query | null>(null),
    [interventions, setInterventions] = useState<
      { variable: string; value: string }[]
    >([{ variable: "Y", value: "1" }]),
    [row, setRow] = useState(0),
    [truth, setTruth] = useState<{
      graph: Graph;
      model: Model;
      description: string;
    } | null>(null),
    [ranks, setRanks] = useState<Rank[]>([]),
    [rankingLabel, setRankingLabel] = useState("");
  const [treatment, setTreatment] = useState("X"),
    [outcome, setOutcome] = useState("Z"),
    [adjustment, setAdjustment] = useState<string[]>([]),
    [backdoor, setBackdoor] = useState<boolean | null>(null);
  const [experimentN, setExperimentN] = useState(100),
    [selectedRank, setSelectedRank] = useState(0),
    [bootstrap, setBootstrap] = useState<unknown>(null),
    [replicates, setReplicates] = useState(10),
    [traceStep, setTraceStep] = useState(-1),
    [replaying, setReplaying] = useState(false);
  const [csv, setCsv] = useState(""),
    [csvName, setCsvName] = useState(""),
    [columns, setColumns] = useState<string[]>([]),
    [selectedColumns, setSelectedColumns] = useState<string[]>([]),
    [csvPersist, setCsvPersist] = useState(false),
    [includeData, setIncludeData] = useState(true),
    [includeTruth, setIncludeTruth] = useState(false),
    [saved, setSaved] = useState(false);
  const [queryRow, setQueryRow] = useState(0);
  const [modal, setModal] = useState<
      "about" | "data" | "model" | "export" | null
    >(null),
    [modelText, setModelText] = useState(""),
    [measuredCSV, setMeasuredCSV] = useState("");
  const fileInput = useRef<HTMLInputElement>(null),
    importInput = useRef<HTMLInputElement>(null),
    measuredInput = useRef<HTMLInputElement>(null),
    lastSnapshot = useRef<unknown>(null),
    cancelled = useRef(false),
    operationEpoch = useRef(0);

  const apply = (next: Session) => {
    setSession(next);
    return next;
  };
  const resetDataset = (next: Session) => {
    setQuery(null);
    setTruth(null);
    setRanks([]);
    setSelected(next.nodes.includes("Y") ? "Y" : next.nodes[0]);
    setSelectionType("node");
    setInterventions([
      {
        variable: next.nodes.includes("Y") ? "Y" : next.nodes[0],
        value: "1",
      },
    ]);
    setTreatment(next.nodes[0]);
    setOutcome(next.nodes[next.nodes.length - 1]);
    setAdjustment([]);
    setBackdoor(null);
    setRow(0);
    setBootstrap(null);
    setReplaying(false);
    setTraceStep(-1);
    setMeasuredCSV("");
    setIncludeTruth(false);
    setIncludeData(next.world !== "csv");
    setSeed(Number(next.seed ?? 7));
    setSamples(next.row_count);
    setWorld(next.world || "csv");
  };
  const persist = async (next: Session) => {
    try {
      const snap = await engine.current!.run("export", {
        include_data: true,
        include_truth: false,
      });
      lastSnapshot.current = snap;
      if ((next.world && next.world !== "csv") || csvPersist) {
        localStorage.setItem(STORAGE, JSON.stringify(snap));
        setSaved(true);
      }
    } catch {
      /* Storage exhaustion must not discard the completed computation. */
    }
  };
  const operation = async <T,>(
    name: string,
    work: () => Promise<T>,
  ): Promise<T | undefined> => {
    if (busy) return;
    const epoch = ++operationEpoch.current;
    setBusy(name);
    setProgress({ stage: name, message: "Computing locally with Python" });
    setError("");
    setNotice("");
    cancelled.current = false;
    try {
      return await work();
    } catch (e) {
      if (epoch === operationEpoch.current && !cancelled.current)
        setError(e instanceof Error ? e.message : String(e));
    } finally {
      if (epoch === operationEpoch.current) setBusy("");
    }
  };
  const runSession = async (
    action: "load" | "restore" | "discover" | "select" | "model" | "experiment",
    payload: unknown,
    onCommit?: (next: Session) => void,
  ) => {
    const epoch = operationEpoch.current;
    const next = (await engine.current!.run(action, payload)) as Session;
    if (epoch !== operationEpoch.current) throw new Error("Cancelled");
    apply(next);
    // The worker has committed this session. Clear dependent results before
    // awaiting storage so cancellation cannot pair new models with old queries.
    setQuery(null);
    setBackdoor(null);
    setBootstrap(null);
    if (action === "load" || action === "restore" || action === "discover") {
      setRanks([]);
      setRankingLabel("");
      setSelectedRank(0);
      setTraceStep(-1);
      setReplaying(false);
    }
    if (action === "load" || action === "restore") {
      resetDataset(next);
      setView("pc");
    }
    if (action === "select" || action === "model") setView("candidate");
    onCommit?.(next);
    await persist(next);
    if (epoch !== operationEpoch.current) throw new Error("Cancelled");
    return next;
  };
  useEffect(() => {
    const e = new Engine((p) => setProgress(p));
    engine.current = e;
    try {
      setSaved(!!localStorage.getItem(STORAGE));
    } catch {
      /* Private browsing may not expose storage. */
    }
    let alive = true;
    (async () => {
      try {
        const s = (await e.run("load", {
          world: "equivalence",
          seed: 7,
          n: 800,
        })) as Session;
        if (!alive || cancelled.current) return;
        apply(s);
        resetDataset(s);
        setBusy("Discovering observational structure");
        const discovered = (await e.run("discover", {
          method: "pc",
          alpha: 0.01,
          max_depth: 3,
        })) as Session;
        if (!alive || cancelled.current) return;
        apply(discovered);
        const snap = await e.run("export", {
          include_data: true,
          include_truth: false,
        });
        lastSnapshot.current = snap;
      } catch (err) {
        if (alive && !cancelled.current)
          setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (alive && operationEpoch.current === 0) setBusy("");
      }
    })();
    return () => {
      alive = false;
      e.dispose();
    };
  }, []);
  useEffect(() => {
    if (!replaying) return;
    const timer = setInterval(
      () =>
        setTraceStep((s) => {
          const count = session?.pc?.trace?.length || 0;
          if (s >= count - 1) {
            setReplaying(false);
            return s;
          }
          return s + 1;
        }),
      1000,
    );
    return () => clearInterval(timer);
  }, [replaying, session?.pc?.trace?.length]);
  useEffect(() => {
    if (!modal) return;
    const close = (e: KeyboardEvent) => {
      if (e.key === "Escape") setModal(null);
    };
    document.addEventListener("keydown", close);
    const oldOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const previous = document.activeElement as HTMLElement | null;
    setTimeout(
      () => document.querySelector<HTMLButtonElement>(".modal-close")?.focus(),
      0,
    );
    return () => {
      document.body.style.overflow = oldOverflow;
      document.removeEventListener("keydown", close);
      previous?.focus();
    };
  }, [modal]);

  useEffect(() => {
    setBackdoor(null);
    setBootstrap(null);
  }, [session?.selected]);

  const loadWorld = () =>
    operation("Observing the system", async () => {
      await runSession("load", { world, seed, n: samples });
      await runSession("discover", { method: "pc", alpha, max_depth: depth });
      go("structure");
    });
  const discover = (method: "pc" | "notears") =>
    operation(
      method === "pc" ? "Running PC-stable" : "Optimizing NOTEARS",
      async () => {
        await runSession(
          "discover",
          {
            method,
            alpha,
            max_depth: depth,
            lambda1: lambda,
            threshold,
            standardize,
          },
          () => setView(method),
        );
        go("structure");
      },
    );
  const selectCandidate = (index: number | string) =>
    operation("Fitting selected explanation", async () => {
      await runSession("select", { index });
      go("query");
    });
  const runQuery = () =>
    operation("Computing model predictions", async () => {
      if (
        new Set(interventions.map((i) => i.variable)).size !==
        interventions.length
      )
        throw new Error("Choose each intervention variable only once.");
      if (interventions.some((i) => !i.value.trim()))
        throw new Error("Enter a numerical value for each intervention.");
      const values = Object.fromEntries(
        interventions
          .filter((i) => i.variable)
          .map((i) => [i.variable, Number(i.value)]),
      );
      if (Object.values(values).some((v) => !Number.isFinite(v)))
        throw new Error("Enter a finite numerical intervention value.");
      const q = (await engine.current!.run("query", {
        interventions: values,
        row,
      })) as Query;
      setQuery(q);
      setQueryRow(row);
      go("query");
    });
  const checkAdjustment = () =>
    operation("Checking backdoor adjustment", async () => {
      const q = (await engine.current!.run("query", {
        interventions: {},
        row: 0,
        treatment,
        outcome,
        adjustment,
      })) as Query;
      setBackdoor(q.backdoor as boolean);
    });
  const rankExperiments = () =>
    operation("Comparing intervention predictions", async () => {
      const r = (await engine.current!.run("rank", {})) as {
        rankings: Rank[];
        label: string;
      };
      setRanks(r.rankings);
      setRankingLabel(r.label);
      setSelectedRank(0);
      go("experiment");
    });
  const runExperiment = (simulate = false) =>
    operation(
      simulate ? "Simulating selected model" : "Running the frozen experiment",
      async () => {
        const r = ranks[selectedRank];
        if (!r) throw new Error("Rank experiments before choosing one.");
        await runSession(
          "experiment",
          {
            variable: r.variable,
            value: r.value,
            n: experimentN,
            score: r.score,
            ...(measuredCSV ? { csv: measuredCSV } : {}),
            ...(simulate ? { simulate_model: true } : {}),
          },
          () => setMeasuredCSV(""),
        );
        setNotice(
          "New experimental evidence scored once. Candidate parameters remain fixed.",
        );
      },
    );
  const revealTruth = () =>
    operation("Revealing simulator truth", async () => {
      setTruth((await engine.current!.run("truth", {})) as typeof truth);
      setView("truth");
    });
  const cancel = () => {
    operationEpoch.current++;
    cancelled.current = true;
    engine.current?.cancel();
    setBusy("");
    setNotice("Computation cancelled. Completed results are preserved.");
    setReplaying(false);
  };
  const restoreSaved = () =>
    operation("Restoring saved experiment", async () => {
      const raw = localStorage.getItem(STORAGE);
      if (!raw) throw new Error("No experiment is saved on this device.");
      await runSession("restore", { experiment: JSON.parse(raw) });
      setNotice(
        "Restored the recorded data, model choices, and experimental history.",
      );
      go("structure");
    });
  const readCSV = async (file: File) => {
    if (file.size > 5 * 1024 * 1024) {
      setError(
        "This file exceeds the 5 MiB upload limit. Choose a smaller CSV.",
      );
      return;
    }
    const text = await file.text();
    const first = text.split(/\r?\n/)[0];
    const names = (first.match(/("(?:[^"]|"")*"|[^,]+)(,|$)/g) || []).map((x) =>
      x.replace(/,$/, "").replace(/^"|"$/g, "").replace(/""/g, '"').trim(),
    );
    setCsv(text);
    setCsvName(file.name);
    setColumns(names);
    setSelectedColumns(names.slice(0, 15));
    setError("");
  };
  const loadCSV = () =>
    operation("Validating local CSV", async () => {
      if (selectedColumns.length < 2)
        throw new Error("Select at least two numerical columns.");
      await runSession("load", { csv, columns: selectedColumns }, (s) => {
        setWorld("csv");
        setSelected(s.nodes[0]);
        setInterventions([{ variable: s.nodes[0], value: "1" }]);
        setCsv("");
      });
      setNotice(
        "CSV loaded locally. Run discovery to inspect its observational structure.",
      );
      go("structure");
    });
  const restoreFile = async (file: File) =>
    operation("Validating experiment file", async () => {
      if (file.size > 25 * 1024 * 1024)
        throw new Error("Experiment exceeds the 25 MiB import limit.");
      const experiment = JSON.parse(await file.text());
      await runSession("restore", { experiment });
      setNotice("Experiment restored from validated JSON.");
      go("structure");
    });
  const currentWorld = worlds.find((w) => w.id === (session?.world || world));
  const currentDiscovery = view === "notears" ? session?.notears : session?.pc;
  const trace = session?.pc?.trace || [];
  const activeTrace = traceStep >= 0 ? trace[traceStep] : undefined;
  const replayGraph =
    traceStep >= 0
      ? (trace
          .slice(0, traceStep + 1)
          .reverse()
          .find((event) => event.graph)?.graph as Graph | undefined)
      : undefined;
  const graph = (view === "truth"
    ? truth?.graph
    : view === "candidate"
      ? candidateGraph(session)
      : view === "notears"
        ? session?.notears?.graph
        : replayGraph || session?.pc?.graph) || {
    ...emptyGraph,
    nodes: session?.nodes || [],
  };
  const nodeIndex = Math.max(
    0,
    session?.nodes.indexOf(
      selectionType === "node" ? selected : session.nodes[0],
    ) ?? 0,
  );
  const selectedNode = session?.nodes[nodeIndex] || "Y";
  const values =
    session?.data?.map((r) => r[nodeIndex]).filter((v) => Number.isFinite(v)) ||
    [];
  const selectedModel = chosenModel(session),
    hasModel = !!selectedModel;
  const currentCandidates = session?.candidates || [];
  const modelLabel =
    session?.selected === "custom"
      ? "User-specified SCM"
      : session?.selected === "notears"
        ? "NOTEARS · OLS refit"
        : `Candidate ${Number(session?.selected ?? 0) + 1} · OLS fit`;
  const edgeEvidence =
    selectionType === "edge"
      ? trace.filter((t) => {
          const [a, b] = selected.split("|");
          const txt = JSON.stringify(t);
          return txt.includes(`"${a}"`) && txt.includes(`"${b}"`);
        })
      : [];
  const canOperate = !busy && !!session;
  const isCSV =
    session?.world === "csv" || (!!session && !session.truth_available);

  const openModel = () => {
    const m = selectedModel || {
      nodes: session!.nodes,
      B: session!.nodes.map(() => session!.nodes.map(() => 0)),
      intercept: session!.nodes.map(() => 0),
      noise_variances: session!.nodes.map(() => 1),
    };
    setModelText(pretty(m));
    setModal("model");
  };
  const go = (next: Section) => {
    setSection(next);
    setReplaying(false);
    window.scrollTo({ top: 0, behavior: "instant" });
  };
  const stepLabel =
    section === "structure"
      ? "01 / Read the structure"
      : section === "experiment"
        ? "02 / Design an experiment"
        : section === "query"
          ? "03 / Ask what if"
          : "04 / Prepare observations";
  const selectedProposal = ranks[selectedRank];
  const graphStatus =
    view === "truth"
      ? "Simulator truth"
      : view === "candidate"
        ? "Assumed model"
        : currentDiscovery
          ? label(currentDiscovery.status)
          : "Not yet computed";
  const assumptions =
    view === "truth"
      ? "Simulator knowledge is revealed separately. Discovery and support are unchanged."
      : view === "candidate"
        ? "Causal answers depend on this selected DAG and its fitted equations."
        : view === "notears"
          ? "An optimization-selected direction is a model choice, not observational proof."
          : "Unresolved directions preserve uncertainty. PC assumes Markov, faithfulness, causal sufficiency, and independent linear Gaussian observations.";
  const candidates = (
    <section className="candidate-section" aria-labelledby="candidates-title">
      <div className="section-heading">
        <div>
          <span className="eyebrow">THE COMPETING EXPLANATIONS</span>
          <h2 id="candidates-title">
            {currentCandidates.length
              ? `${currentCandidates.length} ways to explain the evidence.`
              : "The possibilities begin with data."}
          </h2>
        </div>
        <span className="small-note">
          Select a model to explore its consequences{" "}
          <Icon name="arrow" size={15} />
        </span>
      </div>
      {currentCandidates.length > 0 ? (
        <>
          <div className="candidate-grid">
            {currentCandidates.map((c, i) => (
              <button
                className={`candidate-card ${session?.selected === c.id ? "active" : ""}`}
                key={c.id}
                disabled={!!busy}
                onClick={() => selectCandidate(c.id)}
                aria-pressed={session?.selected === c.id}
              >
                <div className="candidate-heading">
                  <span className="eyebrow">
                    EXPLANATION {String(i + 1).padStart(2, "0")}
                  </span>
                  <span className="candidate-selected">
                    {session?.selected === c.id ? (
                      <>
                        <Icon name="check" size={14} />
                        Selected
                      </>
                    ) : (
                      <Icon name="arrow" size={16} />
                    )}
                  </span>
                </div>
                <CausalGraph graph={c.graph} mini />
                <div className="candidate-support">
                  <span>Relative support</span>
                  <strong>
                    {fmt(c.weight * 100, 1)}
                    <small>%</small>
                  </strong>
                </div>
                <div className="support-track">
                  <span
                    style={{
                      width: `${Math.max(0, Math.min(100, c.weight * 100))}%`,
                    }}
                  />
                </div>
              </button>
            ))}
          </div>
          <p className="caption">
            Normalized plug-in likelihood weights, not posterior probabilities.{" "}
            {session?.enumeration?.complete === false
              ? "Enumeration is truncated; this list is nonexhaustive."
              : "These candidates share the discovered structure. Finite-sample evidence may still be wrong."}
          </p>
        </>
      ) : (
        <div className="empty-state">
          <Icon name="graph" size={32} />
          <h3>No fitted explanations yet.</h3>
          <p>
            {session?.pc
              ? "No valid consistent DAGs are available. Inspect the method diagnostics for conflicts or numerical limitations."
              : "Run PC-stable to enumerate explanations consistent with the observed independences."}
          </p>
          <button
            className="button primary"
            disabled={!canOperate}
            onClick={() => discover("pc")}
          >
            Run PC-stable
            <Icon name="arrow" />
          </button>
        </div>
      )}
    </section>
  );
  const support = (
    <section className="support-section">
      <div className="section-heading">
        <div>
          <span className="eyebrow">EVIDENCE UPDATE</span>
          <h2>Where the support stands.</h2>
        </div>
        <span className="mono">
          {session?.history?.length || 0} completed{" "}
          {session?.history?.length === 1 ? "round" : "rounds"}
        </span>
      </div>
      {currentCandidates.map((c, i) => (
        <div className="support-row" key={c.id}>
          <span>Explanation {String(i + 1).padStart(2, "0")}</span>
          <div className="support-track">
            <span
              style={{
                width: `${Math.max(0, Math.min(100, c.weight * 100))}%`,
              }}
            />
          </div>
          <strong>{fmt(c.weight * 100, 1)}%</strong>
        </div>
      ))}
      <p className="caption">
        Support is conditional on this candidate list and its fixed fitted
        parameters. It is not a probability of causation.
      </p>
    </section>
  );
  const history = !!session?.history?.length && (
    <section className="history-section">
      <div className="section-heading">
        <div>
          <span className="eyebrow">THE EXPERIMENT RECORD</span>
          <h2>A growing body of evidence.</h2>
        </div>
        <span className="mono">
          {session.history.length} {session.history.length === 1 ? "round" : "rounds"}
        </span>
      </div>
      {session.history.map((h, i) => (
        <JsonDetails
          key={i}
          title={`Round ${String(i + 1).padStart(2, "0")} · ${String(h.label || h.batch_id || "experimental batch")}`}
          value={h}
        />
      ))}
    </section>
  );

  return (
    <div className="app-shell">
      <div className="application-content" inert={modal ? true : undefined}>
        <a className="skip-link" href="#workspace">
          Skip to causal workspace
        </a>
        <header className="app-header">
          <button
            className="brand"
            aria-label="Meridian home"
            onClick={() => go("structure")}
          >
            <Mark />
            <span>
              meridian<span className="brand-degree">°</span>
            </span>
          </button>
          <div className="header-description">
            A laboratory for
            <br />
            causal questions.
          </div>
          <div className="runtime-status">
            <span className={`status-dot ${busy ? "working" : ""}`} />
            <span>
              {busy ? "Python is working" : "Computed on your device"}
            </span>
          </div>
          <div className="header-actions">
            <button className="icon-text" aria-label="Field guide" onClick={() => setModal("about")}>
              <Icon name="book" />
              <span>Field guide</span>
            </button>
            <button
              className="icon-text"
              aria-label="Restore"
              onClick={() => importInput.current?.click()}
              disabled={!!busy}
            >
              <Icon name="upload" />
              <span>Restore</span>
            </button>
            <button
              className="button subtle compact"
              disabled={!canOperate}
              aria-label="Export"
              onClick={() => setModal("export")}
            >
              <Icon name="download" />
              <span>Export</span>
            </button>
          </div>
        </header>
        <nav className="task-nav" aria-label="Laboratory workspaces">
          {(
            [
              {
                id: "structure",
                number: "01",
                name: "Structure",
                icon: "graph",
              },
              {
                id: "experiment",
                number: "02",
                name: "Experiments",
                icon: "flask",
              },
              { id: "query", number: "03", name: "What if?", icon: "spark" },
              { id: "data", number: "04", name: "Data", icon: "table" },
            ] as const
          ).map((item) => (
            <button
              key={item.id}
              aria-current={section === item.id ? "page" : undefined}
              className={section === item.id ? "active" : ""}
              onClick={() => go(item.id)}
            >
              <span className="nav-number">{item.number}</span>
              <Icon name={item.icon} size={21} />
              <span>{item.name}</span>
            </button>
          ))}
          <div className="rail-note">OBSERVE. QUESTION. INTERVENE.</div>
        </nav>
        <main id="workspace" tabIndex={-1}>
          <div className="context-bar">
            <span className="eyebrow">{stepLabel}</span>
            <button className="context-source" onClick={() => go("data")}>
              <span className="status-dot" />
              {currentWorld?.short || "Local CSV"}
              <span className="source-detail">
                {session
                  ? `${session.row_count.toLocaleString()} rows · ${isCSV ? "split seed" : "seed"} ${session.seed ?? seed}`
                  : "Initializing"}
              </span>
              <Icon name="chevron" size={14} />
            </button>
          </div>
          {(error || notice) && (
            <div
              className={`notification ${error ? "error" : "success"}`}
              role={error ? "alert" : "status"}
            >
              <Icon name={error ? "info" : "check"} />
              <span>{error || notice}</span>
              <button
                aria-label="Dismiss notification"
                onClick={() => {
                  setError("");
                  setNotice("");
                }}
              >
                <Icon name="close" size={17} />
              </button>
            </div>
          )}
          {session?.world === "hidden" && (
            <div className="warning-note">
              <Icon name="info" />
              <span>
                This system contains an unobserved common cause. The learner
                sees observed variables only and does not detect the hidden
                confounder automatically.
              </span>
            </div>
          )}
          <fieldset
            className="workspace-page operation-controls"
            disabled={!!busy}
            key={section}
          >
            {section === "structure" ? (
              <>
                <div className="folio-intro">
                  <div>
                    <h1>
                      {session?.world === "equivalence" || !session ? (
                        <>
                          Same evidence.
                          <br />
                          <span>Different causes.</span>
                        </>
                      ) : (
                        <>
                          {currentWorld?.short || "Your system."}
                          <br />
                          <span>Open questions.</span>
                        </>
                      )}
                    </h1>
                  </div>
                  <div className="intro-aside">
                    <p>
                      {currentWorld?.description ||
                        session?.description ||
                        "Discover structure in your observations, then test the explanations that remain."}
                    </p>
                    <button
                      className="button primary"
                      disabled={!canOperate || currentCandidates.length < 2}
                      onClick={rankExperiments}
                    >
                      Find the next experiment
                      <Icon name="arrow" size={18} />
                    </button>
                    <span className="caption">
                      Start with what the models disagree on.
                    </span>
                  </div>
                </div>
                <section
                  className="graph-sheet"
                  aria-label="Causal graphs and evidence"
                >
                  <div className="sheet-toolbar">
                    <div className="segmented" aria-label="Graph view">
                      {(["pc", "notears", "candidate"] as const).map((v) => (
                        <button
                          key={v}
                          aria-pressed={view === v}
                          className={view === v ? "active" : ""}
                          onClick={() => setView(v)}
                          disabled={v === "candidate" && !hasModel}
                        >
                          {v === "pc"
                            ? "PC-stable"
                            : v === "notears"
                              ? "NOTEARS"
                              : "Selected model"}
                        </button>
                      ))}
                      {truth && (
                        <button
                          aria-pressed={view === "truth"}
                          className={view === "truth" ? "active" : ""}
                          onClick={() => setView("truth")}
                        >
                          Truth
                        </button>
                      )}
                    </div>
                    <span
                      className={`sheet-status ${view === "truth" || view === "candidate" ? "amber-text" : ""}`}
                    >
                      <span className="status-dot" />
                      {graphStatus}
                    </span>
                  </div>
                  <div className="graph-body">
                    <div className="graph-stage">
                      <div className="graph-annotation">
                        <span>
                          {view === "pc"
                            ? "OBSERVATIONAL STRUCTURE"
                            : view === "notears"
                              ? "OPTIMIZATION-SELECTED GRAPH"
                              : view === "truth"
                                ? "REVEALED GENERATING SYSTEM"
                                : "ONE EXPLICIT EXPLANATION"}
                        </span>
                        <span>
                          {graph.nodes.length} variables /{" "}
                          {graph.directed.length + graph.undirected.length}{" "}
                          relationships
                        </span>
                      </div>
                      {!session ? (
                        <div className="engine-loading">
                          <Mark />
                          <h3>Opening your laboratory.</h3>
                          <p>
                            {progress.message ||
                              "Loading the local Python numerical engine."}
                          </p>
                          {!busy && (
                            <button
                              className="button primary"
                              onClick={loadWorld}
                            >
                              Initialize laboratory
                            </button>
                          )}
                        </div>
                      ) : (
                        <CausalGraph
                          graph={graph}
                          selected={selected}
                          onSelect={(kind, id) => {
                            setSelectionType(kind);
                            setSelected(id);
                          }}
                          conflicts={
                            view === "pc"
                              ? session?.pc?.conflicts || []
                              : currentDiscovery?.conflicts || []
                          }
                        />
                      )}
                      {view === "notears" && !session?.notears && session && (
                        <div className="graph-empty-overlay">
                          <h3>A second way to ask.</h3>
                          <p>
                            Fit a sparse linear model with an acyclicity
                            constraint.
                          </p>
                          <button
                            className="button primary"
                            disabled={!!busy}
                            onClick={() => discover("notears")}
                          >
                            Run NOTEARS
                            <Icon name="play" size={15} />
                          </button>
                        </div>
                      )}
                      <div className="graph-legend">
                        <span>
                          <i className="legend-edge directed" />
                          Directed
                        </span>
                        <span>
                          <i className="legend-edge unresolved" />
                          Unresolved
                        </span>
                        <span className="graph-hint">
                          Select a variable or relationship
                        </span>
                      </div>
                    </div>
                    <aside
                      className="graph-inspector"
                      aria-label="Selected graph element"
                    >
                      <span className="eyebrow">
                        {selectionType === "node"
                          ? "VARIABLE NOTES"
                          : "RELATIONSHIP NOTES"}
                      </span>
                      <h2>
                        {selectionType === "node"
                          ? selectedNode
                          : selected.split("|").join(" — ")}
                      </h2>
                      {selectionType === "node" ? (
                        <>
                          <Histogram values={values} variable={selectedNode} />
                          <p className="caption">
                            Original units. Discovery uses the separate training split.
                          </p>
                        </>
                      ) : (
                        <>
                          <p className="caption">
                            Recorded evidence involving both endpoints. A
                            p-value is not an edge probability.
                          </p>
                          {edgeEvidence.length ? (
                            edgeEvidence
                              .slice(-8)
                              .map((e, i) => (
                                <JsonDetails
                                  key={i}
                                  title={label(
                                    String(
                                      e.type || e.event || `Evidence ${i + 1}`,
                                    ),
                                  )}
                                  value={e}
                                />
                              ))
                          ) : (
                            <p>
                              No removal or orientation evidence recorded for
                              this pair.
                            </p>
                          )}
                        </>
                      )}
                      <button
                        className="text-button"
                        onClick={() => setModal("data")}
                        disabled={!session}
                      >
                        Inspect observations
                        <Icon name="arrow" size={15} />
                      </button>
                    </aside>
                  </div>
                  <div className="sheet-bottom">
                    <p>
                      <Icon name="info" size={16} />
                      {assumptions}
                    </p>
                    <button
                      className="text-button"
                      disabled={!canOperate || !session.truth_available}
                      onClick={revealTruth}
                    >
                      <Icon name="eye" size={16} />
                      {truth ? "View" : "Reveal"} truth
                    </button>
                  </div>
                </section>
                <div className="method-actions">
                  <span className="eyebrow">RECOMPUTE STRUCTURE</span>
                  <button
                    className="button subtle"
                    disabled={!canOperate}
                    onClick={() => discover("pc")}
                  >
                    <Icon name="play" size={14} />
                    Run PC-stable
                  </button>
                  <button
                    className="button subtle"
                    disabled={!canOperate}
                    onClick={() => discover("notears")}
                  >
                    <Icon name="layers" size={15} />
                    {session?.notears ? "Rerun" : "Compare with"} NOTEARS
                  </button>
                  <button className="text-button" onClick={() => go("data")}>
                    <Icon name="sliders" size={15} />
                    Method settings
                  </button>
                </div>
                {candidates}
                <section className="evidence-panel">
                  <div className="section-heading">
                    <div>
                      <span className="eyebrow">AUDIT THE REASONING</span>
                      <h2>Evidence, step by step.</h2>
                    </div>
                    <button
                      className="button subtle"
                      disabled={!trace.length}
                      onClick={() => {
                        if (traceStep >= trace.length - 1) setTraceStep(-1);
                        setReplaying(!replaying);
                        setView("pc");
                      }}
                    >
                      <Icon name={replaying ? "stop" : "play"} size={15} />
                      {replaying ? "Pause" : "Replay"}
                    </button>
                  </div>
                  <p className="caption">
                    {trace.length} recorded events. Actual
                    conditional-independence tests, edge removals, and
                    orientation decisions.
                  </p>
                  {trace.length > 0 && (
                    <>
                      <div className="timeline">
                        <button
                          className={traceStep === -1 ? "active" : ""}
                          onClick={() => {
                            setTraceStep(-1);
                            setReplaying(false);
                            setView("pc");
                          }}
                        >
                          Final graph
                        </button>
                        <input
                          aria-label="Discovery evidence step"
                          type="range"
                          min="0"
                          max={trace.length - 1}
                          value={Math.max(0, traceStep)}
                          onChange={(e) => {
                            setTraceStep(Number(e.target.value));
                            setReplaying(false);
                            setView("pc");
                          }}
                        />
                        <span>
                          {traceStep < 0 ? "—" : traceStep + 1} / {trace.length}
                        </span>
                      </div>
                      {activeTrace && (
                        <div className="trace-event">
                          <span className="trace-index">
                            {String(traceStep + 1).padStart(3, "0")}
                          </span>
                          <div>
                            <h3>
                              {label(
                                String(
                                  activeTrace.type ||
                                    activeTrace.event ||
                                    activeTrace.action ||
                                    "Evidence event",
                                ),
                              )}
                            </h3>
                            <pre>{pretty(activeTrace)}</pre>
                          </div>
                        </div>
                      )}
                    </>
                  )}
                </section>
                <section className="diagnostics-grid">
                  <div>
                    <span className="eyebrow">METHOD REPORTS</span>
                    <h2>Keep the qualifications.</h2>
                    <div className="method-row">
                      <span className="method-icon">PC</span>
                      <div>
                        <strong>PC-stable</strong>
                        <span>
                          {session?.pc
                            ? label(session.pc.status)
                            : "Not computed"}
                        </span>
                      </div>
                      <span className="mono">
                        {session?.pc?.tests ?? "—"} tests
                      </span>
                    </div>
                    {session?.pc && (
                      <JsonDetails
                        title="PC evidence & diagnostics"
                        value={{ ...session.pc, trace: undefined }}
                      />
                    )}
                    <div className="method-row">
                      <span className="method-icon amber">N</span>
                      <div>
                        <strong>Linear NOTEARS</strong>
                        <span>
                          {session?.notears
                            ? label(session.notears.status)
                            : "Not computed"}
                        </span>
                      </div>
                      {session?.notears?.model ? (
                        <button
                          className="text-button"
                          disabled={!!busy}
                          onClick={() => selectCandidate("notears")}
                        >
                          Use fit
                          <Icon name="arrow" size={14} />
                        </button>
                      ) : (
                        <button
                          className="text-button"
                          disabled={!canOperate}
                          onClick={() => discover("notears")}
                        >
                          Run
                          <Icon name="play" size={14} />
                        </button>
                      )}
                    </div>
                    {session?.notears && (
                      <JsonDetails
                        title="NOTEARS optimizer diagnostics"
                        value={session.notears}
                      />
                    )}
                  </div>
                  <div>
                    <span className="eyebrow">UNCERTAINTY, KEPT DISTINCT</span>
                    <h2>How stable is this finding?</h2>
                    <p>
                      Bootstrap frequency measures discovery stability. Effect
                      intervals remain conditional on the selected graph.
                    </p>
                    <div className="inline-controls">
                      <label>
                        Sequential bootstrap replicates
                        <input
                          type="number"
                          min="2"
                          max="30"
                          value={replicates}
                          onChange={(e) =>
                            setReplicates(Number(e.target.value))
                          }
                        />
                      </label>
                      <button
                        className="button subtle"
                        disabled={!canOperate || !hasModel}
                        onClick={() =>
                          operation("Bootstrapping stability", async () =>
                            setBootstrap(
                              await engine.current!.run("bootstrap", {
                                replicates,
                              }),
                            ),
                          )
                        }
                      >
                        <Icon name="layers" size={15} />
                        Run bootstrap
                      </button>
                    </div>
                    {bootstrap != null && (
                      <JsonDetails
                        title="Bootstrap results"
                        value={bootstrap}
                        open
                      />
                    )}
                    <button
                      className="text-button model-action"
                      disabled={!canOperate}
                      onClick={openModel}
                    >
                      <Icon name="code" size={17} />
                      Build an assumed model
                      <Icon name="arrow" size={16} />
                    </button>
                  </div>
                </section>
              </>
            ) : section === "experiment" ? (
              <>
                <div className="folio-intro">
                  <h1>
                    Make the models
                    <br />
                    <span>show their differences.</span>
                  </h1>
                  <div className="intro-aside">
                    <p>
                      Choose an intervention where competing explanations
                      disagree. Then let new evidence change their support.
                    </p>
                    <button
                      className="button primary"
                      disabled={!canOperate || currentCandidates.length < 2}
                      onClick={rankExperiments}
                    >
                      {ranks.length ? "Recompute" : "Rank"} experiment proposals
                      <Icon name="arrow" size={17} />
                    </button>
                  </div>
                </div>
                {ranks.length > 0 && selectedProposal ? (
                  <div className="experiment-layout">
                    <section className="proposal-list">
                      <div className="section-heading">
                        <div>
                          <span className="eyebrow">
                            PREDICTIVE DISAGREEMENT
                          </span>
                          <h2>Questions worth asking.</h2>
                        </div>
                        <span className="tag">Heuristic score</span>
                      </div>
                      <p className="caption">
                        Mean and covariance disagreement in fixed training-data
                        units. No simulator truth is used.
                      </p>
                      <div className="ranking-head">
                        <span>Intervention</span>
                        <span>Disagreement</span>
                      </div>
                      {ranks.slice(0, 12).map((r, i) => (
                        <button
                          key={i}
                          disabled={!!busy}
                          className={`rank-option ${selectedRank === i ? "active" : ""}`}
                          onClick={() => setSelectedRank(i)}
                          aria-pressed={selectedRank === i}
                        >
                          <span className="rank-number">
                            {String(i + 1).padStart(2, "0")}
                          </span>
                          <span className="rank-formula">
                            <strong>
                              do({r.variable} = {fmt(r.value, 2)})
                            </strong>
                            <small>
                              mean {fmt(r.mean_score, 3)} / cov{" "}
                              {fmt(r.covariance_score, 3)}
                            </small>
                          </span>
                          <span className="rank-score">{fmt(r.score, 3)}</span>
                          <Icon name="arrow" size={18} />
                        </button>
                      ))}
                      <JsonDetails
                        title="Ranking settings & complete scores"
                        value={{ label: rankingLabel, rankings: ranks }}
                      />
                    </section>
                    <section className="experiment-plan">
                      <span className="eyebrow">YOUR EXPERIMENT PLAN</span>
                      <div className="plan-equation">
                        <span>do</span>
                        <strong>
                          {selectedProposal.variable}
                          <span> = </span>
                          {fmt(selectedProposal.value, 2)}
                        </strong>
                      </div>
                      <p>
                        Replace the equation for{" "}
                        <strong>{selectedProposal.variable}</strong> with a
                        fixed value. Observe how the rest of the system
                        responds.
                      </p>
                      <label>
                        New observations per batch
                        <input
                          type="number"
                          min="20"
                          max="1000"
                          step="10"
                          value={experimentN}
                          onChange={(e) =>
                            setExperimentN(Number(e.target.value))
                          }
                        />
                      </label>
                      <div className="plan-rule">
                        <span>01</span>
                        <p>
                          Freeze the plan, sample count, and score before
                          outcomes.
                        </p>
                      </div>
                      <div className="plan-rule">
                        <span>02</span>
                        <p>
                          Score only nonintervened mechanisms. Keep fitted
                          parameters fixed.
                        </p>
                      </div>
                      {isCSV ? (
                        <>
                          <div className="warning-note">
                            Your CSV has no experiment oracle.
                          </div>
                          <button
                            className="button subtle full"
                            disabled={!!busy}
                            onClick={() => measuredInput.current?.click()}
                          >
                            <Icon name="upload" size={15} />
                            {measuredCSV
                              ? "Measured batch ready"
                              : "Import measured CSV batch"}
                          </button>
                          {measuredCSV && (
                            <button
                              className="button primary full"
                              disabled={!!busy}
                              onClick={() => runExperiment()}
                            >
                              Score measured evidence
                            </button>
                          )}
                          <button
                            className="button subtle full"
                            disabled={!!busy || !hasModel}
                            onClick={() => runExperiment(true)}
                          >
                            Simulate selected model only
                          </button>
                          <p className="caption">
                            A model simulation is hypothetical, not real-world
                            evidence.
                          </p>
                        </>
                      ) : (
                        <>
                          <button
                            className="button primary full"
                            disabled={!!busy}
                            onClick={() => runExperiment()}
                          >
                            Run simulated experiment
                            <Icon name="play" size={16} />
                          </button>
                          <p className="caption">
                            A fresh batch from the built-in simulator.
                          </p>
                        </>
                      )}
                    </section>
                  </div>
                ) : (
                  <div className="empty-state experiment-empty">
                    <Icon name="flask" size={40} />
                    <h2>Observation is only the beginning.</h2>
                    <p>
                      {currentCandidates.length < 2
                        ? "At least two fitted candidates are needed to compare predictions. Return to Structure to discover competing explanations."
                        : "Rank interventions to find where your fitted candidates predict different outcomes."}
                    </p>
                    {currentCandidates.length < 2 && (
                      <button
                        className="button subtle"
                        onClick={() => go("structure")}
                      >
                        Explore the structure
                        <Icon name="arrow" />
                      </button>
                    )}
                  </div>
                )}
                {currentCandidates.length > 0 && support}
                {history}
                {candidates}
              </>
            ) : section === "query" ? (
              <>
                <div className="folio-intro">
                  <h1>
                    Change one cause.
                    <br />
                    <span>Follow the consequences.</span>
                  </h1>
                  <div className="intro-aside">
                    <p>
                      Observing a value and setting it are different questions.
                      Explore both under one explicit structural model.
                    </p>
                    <button
                      className="text-button"
                      disabled={!canOperate}
                      onClick={openModel}
                    >
                      <Icon name="code" size={17} />
                      Build an assumed model
                      <Icon name="arrow" size={17} />
                    </button>
                  </div>
                </div>
                <div className="query-layout">
                  <section className="query-controls">
                    <span className="eyebrow">THE ASSUMPTION</span>
                    <div className="model-badge">
                      <Icon name="graph" size={18} />
                      {hasModel
                        ? modelLabel
                        : "Select a fitted candidate first"}
                    </div>
                    {hasModel && (
                      <CausalGraph
                        graph={candidateGraph(session)!}
                        mini
                        interventions={interventions.map((i) => i.variable)}
                      />
                    )}
                    <p className="caption">
                      Original model · intervention targets highlighted
                    </p>
                    <button
                      className="text-button"
                      onClick={() => go("structure")}
                    >
                      Compare explanations
                      <Icon name="arrow" size={14} />
                    </button>
                    <div className="query-inputs">
                      <span className="eyebrow">THE INTERVENTION</span>
                      {interventions.map((item, i) => (
                        <div className="intervention-row" key={i}>
                          <label>
                            Set variable
                            <select
                              aria-label={`Intervention variable ${i + 1}`}
                              value={item.variable}
                              onChange={(e) => {
                                setInterventions(
                                  interventions.map((a, j) =>
                                    j === i
                                      ? { ...a, variable: e.target.value }
                                      : a,
                                  ),
                                );
                                setQuery(null);
                              }}
                            >
                              {session?.nodes.map((n) => (
                                <option key={n} value={n}>
                                  {n}
                                </option>
                              ))}
                            </select>
                          </label>
                          <span className="equals">=</span>
                          <label>
                            To value
                            <input
                              aria-label={`Intervention value ${i + 1}`}
                              type="number"
                              step=".1"
                              value={item.value}
                              onChange={(e) => {
                                setInterventions(
                                  interventions.map((a, j) =>
                                    j === i
                                      ? { ...a, value: e.target.value }
                                      : a,
                                  ),
                                );
                                setQuery(null);
                              }}
                            />
                          </label>
                          {interventions.length > 1 && (
                            <button
                              className="remove-intervention"
                              aria-label={`Remove intervention ${i + 1}`}
                              onClick={() => {
                                setInterventions(
                                  interventions.filter((_, j) => i !== j),
                                );
                                setQuery(null);
                              }}
                            >
                              <Icon name="close" size={15} />
                            </button>
                          )}
                        </div>
                      ))}
                      <button
                        className="text-button add-intervention"
                        disabled={
                          interventions.length >= (session?.nodes.length || 0)
                        }
                        onClick={() => {
                          setInterventions([
                            ...interventions,
                            {
                              variable:
                                session?.nodes.find(
                                  (n) =>
                                    !interventions.some(
                                      (i) => i.variable === n,
                                    ),
                                ) || "",
                              value: "0",
                            },
                          ]);
                          setQuery(null);
                        }}
                      >
                        + Add simultaneous intervention
                      </button>
                      <label>
                        Factual observation row
                        <input
                          type="number"
                          min="0"
                          max={(session?.row_count || 1) - 1}
                          value={row}
                          onChange={(e) => {
                            setRow(Number(e.target.value));
                            setQuery(null);
                          }}
                        />
                      </label>
                      <button
                        className="button primary full"
                        disabled={!canOperate || !hasModel}
                        onClick={runQuery}
                      >
                        Compute what changes
                        <Icon name="arrow" size={17} />
                      </button>
                      <p className="caption">
                        Causal answers are conditional on this fitted model, not
                        proven by the data.
                      </p>
                    </div>
                  </section>
                  <section className="query-results" aria-live="polite">
                    {query ? (
                      <>
                        <div className="section-heading">
                          <div>
                            <span className="eyebrow">OBSERVE ≠ INTERVENE</span>
                            <h2>Two questions. Two distributions.</h2>
                          </div>
                          <label>
                            Outcome variable
                            <select
                              value={selectedNode}
                              onChange={(e) => {
                                setSelected(e.target.value);
                                setSelectionType("node");
                              }}
                            >
                              {query.nodes.map((n) => (
                                <option key={n}>{n}</option>
                              ))}
                            </select>
                          </label>
                        </div>
                        <DistributionChart
                          observational={query.conditional}
                          interventional={query.interventional}
                          index={Math.max(0, query.nodes.indexOf(selectedNode))}
                        />
                        <div className="result-table-wrap">
                          <table className="result-table">
                            <thead>
                              <tr>
                                <th>Variable</th>
                                <th>Condition mean</th>
                                <th>Intervention mean</th>
                              </tr>
                            </thead>
                            <tbody>
                              {query.nodes.map((n, i) => (
                                <tr key={n}>
                                  <th scope="row">{n}</th>
                                  <td className="amber-text">
                                    {fmt(query.conditional.mean[i])}
                                  </td>
                                  <td className="teal-text">
                                    {fmt(query.interventional.mean[i])}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                        <JsonDetails
                          title="Means, variances & replaced equations"
                          value={{
                            model: query.model_label,
                            observational: query.observational,
                            conditional: query.conditional,
                            interventional: query.interventional,
                            descendants: query.descendants,
                            equations: query.equations,
                            effects: query.effects,
                          }}
                        />
                        <div className="counterfactual-results">
                          <span className="eyebrow">
                            THE SAME INDIVIDUAL. A DIFFERENT WORLD.
                          </span>
                          <h2>Counterfactual · row {queryRow}</h2>
                          <div className="result-table-wrap">
                            <table className="result-table">
                              <thead>
                                <tr>
                                  <th>Variable</th>
                                  <th>Factual</th>
                                  <th>What if</th>
                                  <th>Change</th>
                                </tr>
                              </thead>
                              <tbody>
                                {query.nodes.map((n, i) => {
                                  const delta =
                                    query.counterfactual[i] - query.factual[i];
                                  return (
                                    <tr
                                      key={n}
                                      className={
                                        Math.abs(delta) > 1e-8
                                          ? "changed-row"
                                          : ""
                                      }
                                    >
                                      <th scope="row">{n}</th>
                                      <td>{fmt(query.factual[i])}</td>
                                      <td>{fmt(query.counterfactual[i])}</td>
                                      <td>
                                        {delta > 1e-8 ? "+" : ""}
                                        {fmt(
                                          Math.abs(delta) < 1e-8 ? 0 : delta,
                                        )}
                                      </td>
                                    </tr>
                                  );
                                })}
                              </tbody>
                            </table>
                          </div>
                          <p className="caption">
                            Abduction → action → prediction. This observation’s
                            model-specific residuals stay fixed. No new noise is
                            sampled.
                          </p>
                        </div>
                      </>
                    ) : (
                      <div className="query-empty">
                        <div className="question-pair">
                          <span>P(Y | X = x)</span>
                          <span>≠</span>
                          <span>P(Y | do(X = x))</span>
                        </div>
                        <h2>Seeing is not setting.</h2>
                        <p>
                          Choose a variable and a value, then compute. Meridian
                          compares conditioning with intervention and traces a
                          counterfactual for one observation.
                        </p>
                        <div className="query-sequence">
                          <span>
                            <b>01</b> Choose a model
                          </span>
                          <span>
                            <b>02</b> Replace an equation
                          </span>
                          <span>
                            <b>03</b> Compare outcomes
                          </span>
                        </div>
                      </div>
                    )}
                  </section>
                </div>
                <section className="backdoor-section">
                  <div>
                    <span className="eyebrow">
                      CHECK THE GRAPHICAL CRITERION
                    </span>
                    <h2>What needs adjusting?</h2>
                    <p>
                      Test a supplied set against the selected DAG. This checks
                      the backdoor criterion under that model, not whether its
                      causal assumptions hold.
                    </p>
                  </div>
                  <div>
                    <div className="backdoor-controls">
                      <label>
                        Treatment
                        <select
                          value={treatment}
                          onChange={(e) => {
                            setTreatment(e.target.value);
                            setAdjustment(
                              adjustment.filter((n) => n !== e.target.value),
                            );
                            setBackdoor(null);
                          }}
                        >
                          {session?.nodes.map((n) => (
                            <option key={n}>{n}</option>
                          ))}
                        </select>
                      </label>
                      <label>
                        Outcome
                        <select
                          value={outcome}
                          onChange={(e) => {
                            setOutcome(e.target.value);
                            setAdjustment(
                              adjustment.filter((n) => n !== e.target.value),
                            );
                            setBackdoor(null);
                          }}
                        >
                          {session?.nodes.map((n) => (
                            <option key={n}>{n}</option>
                          ))}
                        </select>
                      </label>
                    </div>
                    <div className="adjustment-options">
                      {session?.nodes
                        .filter((n) => n !== treatment && n !== outcome)
                        .map((n) => (
                          <label key={n}>
                            <input
                              type="checkbox"
                              checked={adjustment.includes(n)}
                              onChange={(e) => {
                                setAdjustment(
                                  e.target.checked
                                    ? [...adjustment, n]
                                    : adjustment.filter((a) => a !== n),
                                );
                                setBackdoor(null);
                              }}
                            />
                            {n}
                          </label>
                        ))}
                    </div>
                    <div className="adjustment-submit">
                      <span className="mono">
                        Set:{" "}
                        {adjustment.length
                          ? `{${adjustment.join(", ")}}`
                          : "∅ (no adjustment)"}
                      </span>
                      <button
                        className="button subtle"
                        disabled={
                          !canOperate || !hasModel || treatment === outcome
                        }
                        onClick={checkAdjustment}
                      >
                        Check supplied set
                        <Icon name="check" size={15} />
                      </button>
                    </div>
                    {backdoor !== null && (
                      <div
                        className={`backdoor-result ${backdoor ? "" : "invalid"}`}
                        role="status"
                      >
                        <strong>
                          {backdoor
                            ? "Valid backdoor adjustment set"
                            : "This set fails the backdoor criterion"}
                        </strong>
                        <p>
                          For {treatment} → {outcome} in {modelLabel}.{" "}
                          {backdoor
                            ? "The set blocks all backdoor paths and includes no treatment descendants."
                            : "This checks only the supplied set, not every possible set."}
                        </p>
                      </div>
                    )}
                  </div>
                </section>
              </>
            ) : (
              <>
                <div className="folio-intro">
                  <h1>
                    Start with observations.
                    <br />
                    <span>Keep the causes open.</span>
                  </h1>
                  <div className="intro-aside">
                    <p>
                      Explore a known system or bring your own numerical
                      observations. Everything runs locally in your browser.
                    </p>
                    <span className="privacy-line">
                      <Icon name="lock" size={17} />
                      Your data stays on this device.
                    </span>
                  </div>
                </div>
                <div className="data-layout">
                  <section className="world-section">
                    <span className="eyebrow">
                      FIVE SYSTEMS, FIVE QUESTIONS
                    </span>
                    <div className="world-list">
                      {worlds.map((w) => (
                        <button
                          key={w.id}
                          onClick={() => setWorld(w.id)}
                          className={`world-option ${world === w.id ? "active" : ""}`}
                          aria-pressed={world === w.id}
                        >
                          <span className="world-number">{w.number}</span>
                          <span>
                            <strong>{w.name}</strong>
                            <small>{w.description}</small>
                          </span>
                          {world === w.id ? (
                            <Icon name="check" size={19} />
                          ) : (
                            <Icon name="arrow" size={19} />
                          )}
                        </button>
                      ))}
                    </div>
                    <div className="dataset-settings">
                      <label>
                        Observations
                        <select
                          value={samples}
                          onChange={(e) => setSamples(Number(e.target.value))}
                        >
                          {![300, 800, 1500, 3000, 5000].includes(samples) && (
                            <option value={samples}>{samples} rows</option>
                          )}
                          <option value={300}>300 rows</option>
                          <option value={800}>800 rows</option>
                          <option value={1500}>1,500 rows</option>
                          <option value={3000}>3,000 rows</option>
                          <option value={5000}>5,000 rows</option>
                        </select>
                      </label>
                      <label>
                        Random seed
                        <input
                          type="number"
                          min="0"
                          max="999999"
                          value={seed}
                          onChange={(e) =>
                            setSeed(numberInput(e.target.value, 7))
                          }
                        />
                      </label>
                      <button
                        className="button primary"
                        disabled={!!busy || world === "csv"}
                        onClick={loadWorld}
                      >
                        Generate & discover
                        <Icon name="arrow" size={17} />
                      </button>
                    </div>
                  </section>
                  <section className="import-section">
                    <span className="eyebrow">YOUR OWN EVIDENCE</span>
                    <h2>
                      Local data.
                      <br />
                      Open possibilities.
                    </h2>
                    <p>
                      Complete, continuous observations. Choose 2–15 numerical
                      columns from a CSV up to 5 MiB.
                    </p>
                    <button
                      className="upload-zone"
                      disabled={!!busy}
                      onClick={() => fileInput.current?.click()}
                    >
                      <Icon name="upload" size={28} />
                      <strong>Open a local CSV</strong>
                      <span>Processed on this device</span>
                    </button>
                    {csv && (
                      <div className="csv-selection">
                        <strong>{csvName}</strong>
                        <p>Select complete numerical columns.</p>
                        <div className="column-choices">
                          {columns.map((c, i) => (
                            <label key={`${c}-${i}`}>
                              <input
                                type="checkbox"
                                checked={selectedColumns.includes(c)}
                                onChange={(e) =>
                                  setSelectedColumns(
                                    e.target.checked
                                      ? [...selectedColumns, c]
                                      : selectedColumns.filter((x) => x !== c),
                                  )
                                }
                              />
                              {c}
                            </label>
                          ))}
                        </div>
                        <label className="check-label">
                          <input
                            type="checkbox"
                            checked={csvPersist}
                            onChange={(e) => setCsvPersist(e.target.checked)}
                          />
                          Save raw data on this device
                        </label>
                        <button
                          className="button primary full"
                          disabled={!!busy}
                          onClick={loadCSV}
                        >
                          Validate & load CSV
                          <Icon name="arrow" size={16} />
                        </button>
                      </div>
                    )}
                    {saved && (
                      <button
                        className="text-button restore-saved"
                        disabled={!!busy}
                        onClick={restoreSaved}
                      >
                        <Icon name="reset" size={15} />
                        Restore last saved investigation
                      </button>
                    )}
                  </section>
                </div>
                {session && (
                  <section className="observations-section">
                    <div className="section-heading">
                      <div>
                        <span className="eyebrow">CURRENT OBSERVATIONS</span>
                        <h2>A window into your evidence.</h2>
                      </div>
                      <button
                        className="button subtle"
                        onClick={() => setModal("data")}
                      >
                        Inspect data preview
                        <Icon name="arrow" size={16} />
                      </button>
                    </div>
                    <div className="data-numbers">
                      <div>
                        <strong>{session.row_count.toLocaleString()}</strong>
                        <span>observations</span>
                      </div>
                      <div>
                        <strong>{session.nodes.length}</strong>
                        <span>variables</span>
                      </div>
                      <div>
                        <strong>
                          64<span>bit</span>
                        </strong>
                        <span>numerical precision</span>
                      </div>
                      <div>
                        <strong>{String(session.seed ?? "—")}</strong>
                        <span>random seed</span>
                      </div>
                    </div>
                    <div className="result-table-wrap">
                      <table className="result-table preview-table">
                        <thead>
                          <tr>
                            <th>Row</th>
                            {session.nodes.map((n) => (
                              <th key={n}>{n}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {session.data.slice(0, 6).map((r, i) => (
                            <tr key={i}>
                              <th scope="row">{String(i).padStart(3, "0")}</th>
                              {r.map((v, j) => (
                                <td key={j}>{fmt(v, 4)}</td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <JsonDetails
                      title="Data quality & split"
                      value={{
                        diagnostics: session.diagnostics,
                        split: session.split,
                      }}
                    />
                  </section>
                )}
                <section className="settings-section">
                  <div className="section-heading">
                    <div>
                      <span className="eyebrow">METHOD SETTINGS</span>
                      <h2>Make every assumption explicit.</h2>
                    </div>
                    <p className="caption">
                      Changes take effect on the next computation.
                    </p>
                  </div>
                  <div className="settings-grid">
                    <div>
                      <span className="method-icon">PC</span>
                      <h3>Conditional independence</h3>
                      <p>
                        PC-stable removes edges using Fisher-z tests and orients
                        only the directions supported by its rules.
                      </p>
                      <div className="control-grid">
                        <label>
                          PC significance level α
                          <input
                            type="number"
                            step=".005"
                            min=".001"
                            max=".2"
                            value={alpha}
                            onChange={(e) => setAlpha(Number(e.target.value))}
                          />
                        </label>
                        <label>
                          Maximum conditioning depth
                          <input
                            type="number"
                            min="0"
                            max="5"
                            value={depth}
                            onChange={(e) => setDepth(Number(e.target.value))}
                          />
                        </label>
                      </div>
                      <button
                        className="button subtle"
                        disabled={!canOperate}
                        onClick={() => discover("pc")}
                      >
                        Run PC-stable
                        <Icon name="play" size={14} />
                      </button>
                    </div>
                    <div>
                      <span className="method-icon amber">N</span>
                      <h3>Sparse optimization</h3>
                      <p>
                        Linear NOTEARS is scale-sensitive. A selected direction
                        is a model choice, not causal proof.
                      </p>
                      <div className="control-grid">
                        <label>
                          NOTEARS L1 penalty
                          <input
                            type="number"
                            min="0"
                            step=".05"
                            value={lambda}
                            onChange={(e) => setLambda(Number(e.target.value))}
                          />
                        </label>
                        <label>
                          NOTEARS edge threshold
                          <input
                            type="number"
                            min="0"
                            step=".05"
                            value={threshold}
                            onChange={(e) =>
                              setThreshold(Number(e.target.value))
                            }
                          />
                        </label>
                      </div>
                      <label className="check-label">
                        <input
                          type="checkbox"
                          checked={standardize}
                          onChange={(e) => setStandardize(e.target.checked)}
                        />
                        Standardize NOTEARS input
                      </label>
                      <button
                        className="button subtle"
                        disabled={!canOperate}
                        onClick={() => discover("notears")}
                      >
                        Run NOTEARS
                        <Icon name="play" size={14} />
                      </button>
                    </div>
                  </div>
                </section>
              </>
            )}
          </fieldset>
          <footer className="app-footer">
            <span>
              <Mark />
              MERIDIAN / A CAUSAL LABORATORY
            </span>
            <span>Linear · Gaussian · Acyclic</span>
            <button className="text-button" onClick={() => setModal("about")}>
              Know the assumptions
              <Icon name="arrow" size={14} />
            </button>
          </footer>
        </main>
        {busy && (
          <div className="progress-toast" role="status" aria-live="polite">
            <span className="spinner" />
            <div>
              <strong>{busy}</strong>
              <span>
                {progress.message || label(progress.stage)}
                {progress.completed !== undefined
                  ? ` · ${progress.completed}${progress.total ? ` / ${progress.total}` : ""}`
                  : ""}
              </span>
            </div>
            <button className="button subtle compact" onClick={cancel}>
              <Icon name="stop" size={13} />
              Cancel
            </button>
          </div>
        )}
      </div>
      <input
        ref={fileInput}
        type="file"
        accept=".csv,text/csv"
        hidden
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) void readCSV(file);
          e.target.value = "";
        }}
      />
      <input
        ref={importInput}
        type="file"
        accept=".json,application/json"
        hidden
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) void restoreFile(f);
          e.target.value = "";
        }}
      />
      <input
        ref={measuredInput}
        type="file"
        accept=".csv,text/csv"
        hidden
        onChange={async (e) => {
          const f = e.target.files?.[0];
          if (f) {
            if (f.size > 5 * 1024 * 1024)
              setError("Measured batch exceeds the 5 MiB limit.");
            else setMeasuredCSV(await f.text());
          }
          e.target.value = "";
        }}
      />
      {modal && (
        <div
          className="modal-backdrop"
          onClick={(e) => {
            if (e.target === e.currentTarget) setModal(null);
          }}
        >
          <section
            className={`modal ${modal === "data" ? "wide" : ""}`}
            role="dialog"
            aria-modal="true"
            aria-labelledby="modal-title"
            onKeyDown={(e) => {
              if (e.key === "Tab") {
                const els = e.currentTarget.querySelectorAll<HTMLElement>(
                  'button:not(:disabled),input,select,textarea,[tabindex="0"]',
                );
                const first = els[0],
                  last = els[els.length - 1];
                if (e.shiftKey && document.activeElement === first) {
                  e.preventDefault();
                  last?.focus();
                } else if (!e.shiftKey && document.activeElement === last) {
                  e.preventDefault();
                  first?.focus();
                }
              }
            }}
          >
            <button
              className="modal-close"
              onClick={() => setModal(null)}
              aria-label="Close dialog"
            >
              <Icon name="close" />
            </button>
            {error && (
              <div className="notification error" role="alert">
                {error}
              </div>
            )}
            {modal === "about" ? (
              <>
                <span className="eyebrow">THE MERIDIAN FIELD GUIDE</span>
                <h2 id="modal-title">
                  Good causal questions
                  <br />
                  start with clear assumptions.
                </h2>
                <p>
                  Meridian is a small causal machine learning laboratory. Python
                  computes the graphs, statistical evidence, fitted equations,
                  and interventions locally in your browser.
                </p>
                <div className="guide-grid">
                  <article>
                    <span>01</span>
                    <h3>Observe</h3>
                    <p>
                      Associations describe how measured variables vary
                      together. Conditioning asks what is typical among
                      observations with a given value.
                    </p>
                  </article>
                  <article>
                    <span>02</span>
                    <h3>Discover</h3>
                    <p>
                      PC-stable tests conditional independences. It can leave
                      causal directions unresolved. NOTEARS selects a sparse
                      directed model by optimization.
                    </p>
                  </article>
                  <article>
                    <span>03</span>
                    <h3>Intervene</h3>
                    <p>
                      An intervention replaces a structural equation. Candidate
                      models that fit the same observations can predict
                      different experimental outcomes.
                    </p>
                  </article>
                  <article>
                    <span>04</span>
                    <h3>Ask what if</h3>
                    <p>
                      A counterfactual keeps one observation’s model-specific
                      residuals fixed, then propagates an intervention through
                      that selected SCM.
                    </p>
                  </article>
                </div>
                <div className="guide-assumptions">
                  <h3>The scope is deliberate.</h3>
                  <p>
                    Complete continuous observations, modest acyclic linear
                    models, additive Gaussian noise. PC causal interpretation
                    assumes causal Markov, faithfulness, causal sufficiency, and
                    independent sampling. Hidden confounding, nonlinear effects,
                    missingness, and time series are outside the supported
                    discovery scope.
                  </p>
                  <p>
                    Candidate support is a normalized plug-in likelihood, not a
                    Bayesian posterior. Bootstrap frequency is stability, not
                    causal probability. A bounded candidate list is not a
                    complete identified set.
                  </p>
                </div>
              </>
            ) : modal === "data" ? (
              <>
                <span className="eyebrow">ORIGINAL UNITS · LOCAL DATA</span>
                <h2 id="modal-title">A window into the observations.</h2>
                <p>
                  {session?.row_count.toLocaleString()} total rows · first{" "}
                  {session?.data.length} shown. Training, validation, and
                  evaluation roles are recorded separately.
                </p>
                <div className="data-table-scroll">
                  <table className="result-table">
                    <thead>
                      <tr>
                        <th>Row</th>
                        {session?.nodes.map((n) => (
                          <th key={n}>{n}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {session?.data.map((r, i) => (
                        <tr
                          key={i}
                          onClick={() => {
                            setRow(i);
                            setQuery(null);
                            go("query");
                            setModal(null);
                          }}
                          tabIndex={0}
                          aria-label={`Use row ${i} for counterfactual`}
                          onKeyDown={(e) => {
                            if (e.key === "Enter" || e.key === " ") {
                              e.preventDefault();
                              setRow(i);
                              setQuery(null);
                              go("query");
                              setModal(null);
                            }
                          }}
                        >
                          <td className="row-index">{i}</td>
                          {r.map((v, j) => (
                            <td key={j}>{fmt(v, 4)}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="helper-text">
                  Select a row to use it as a factual observation for a
                  counterfactual.
                </p>
                <JsonDetails
                  title="Validation diagnostics"
                  value={session?.diagnostics}
                />
              </>
            ) : modal === "model" ? (
              <>
                <span className="eyebrow">USER-SPECIFIED ASSUMPTIONS</span>
                <h2 id="modal-title">Write an explicit structural model.</h2>
                <p>
                  Use the existing variable IDs. Matrix convention:{" "}
                  <code>B[child, parent]</code>. Acyclicity, finite
                  coefficients, and strictly positive noise variances are
                  validated in Python.
                </p>
                <label htmlFor="model-json">Model JSON</label>
                <textarea
                  id="model-json"
                  className="model-editor"
                  spellCheck={false}
                  value={modelText}
                  onChange={(e) => setModelText(e.target.value)}
                />
                <div className="modal-actions">
                  <button
                    className="button subtle"
                    onClick={() => setModal(null)}
                  >
                    Cancel
                  </button>
                  <button
                    className="button primary"
                    disabled={!!busy}
                    onClick={() =>
                      operation("Validating assumed model", async () => {
                        await runSession("model", JSON.parse(modelText));
                        go("query");
                        setModal(null);
                      })
                    }
                  >
                    Validate & select model
                    <Icon name="arrow" size={15} />
                  </button>
                </div>
              </>
            ) : (
              <>
                <span className="eyebrow">A REPRODUCIBLE INVESTIGATION</span>
                <h2 id="modal-title">Take your experiment with you.</h2>
                <p>
                  Export versioned JSON with settings, seed, evidence, selected
                  models, and recorded experimental outcomes. Imported JSON is
                  validated; no code is executed.
                </p>
                <label className="export-option">
                  <input
                    type="checkbox"
                    checked={includeData}
                    onChange={(e) => setIncludeData(e.target.checked)}
                  />
                  <span>
                    <strong>Include raw observations</strong>
                    <small>
                      Required for restoring fits and further analysis. Uploaded
                      raw data is included only when checked.
                    </small>
                  </span>
                </label>
                {session?.truth_available && (
                  <label className="export-option">
                    <input
                      type="checkbox"
                      checked={includeTruth}
                      onChange={(e) => setIncludeTruth(e.target.checked)}
                    />
                    <span>
                      <strong>Include simulator truth</strong>
                      <small>
                        Keep generating equations separate from learner inputs.
                      </small>
                    </span>
                  </label>
                )}
                <div className="modal-actions">
                  <button
                    className="button primary"
                    disabled={!!busy}
                    onClick={() =>
                      operation("Exporting experiment", async () => {
                        const result = await engine.current!.run("export", {
                          include_data: includeData,
                          include_truth: includeTruth,
                        });
                        download(
                          `meridian-${session?.world || "experiment"}-${seed}.json`,
                          result,
                        );
                        setModal(null);
                      })
                    }
                  >
                    <Icon name="download" size={16} />
                    Download experiment JSON
                  </button>
                </div>
              </>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
