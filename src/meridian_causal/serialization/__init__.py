"""Bounded, data-only JSON validation. No pickle, imported code, or eval."""
import json
import math

MAX_JSON_BYTES = 12 * 1024 * 1024


def validate_json_tree(value):
    count = 0
    def visit(item, depth):
        nonlocal count
        count += 1
        if count > 1_000_000 or depth > 24:
            raise ValueError('Experiment exceeds the supported size or nesting limit.')
        if isinstance(item, dict):
            if len(item) > 10000 or any(not isinstance(k, str) or len(k) > 200 for k in item):
                raise ValueError('Invalid JSON object keys or size.')
            for sub in item.values(): visit(sub,depth+1)
        elif isinstance(item,list):
            if len(item)>30000: raise ValueError('Experiment array exceeds its size limit.')
            for sub in item: visit(sub,depth+1)
        elif isinstance(item,float):
            if not math.isfinite(item): raise ValueError('Experiment numbers must be finite.')
        elif isinstance(item,str):
            if len(item)>20000: raise ValueError('Experiment string exceeds its size limit.')
        elif item is not None and not isinstance(item,(bool,int)):
            raise ValueError('Only JSON data types are supported.')
        elif isinstance(item,int) and abs(item)>2**53:
            raise ValueError('Integer exceeds portable JSON precision.')
    visit(value,0)
    return value


def loads(text):
    if not isinstance(text,str) or len(text.encode())>MAX_JSON_BYTES:
        raise ValueError('Experiment exceeds the 12 MiB import limit.')
    def unique_object(pairs):
        result={}
        for key,value in pairs:
            if key in result:
                raise ValueError(f'Duplicate JSON object key: {key!r}.')
            result[key]=value
        return result
    try:
        result=json.loads(text,object_pairs_hook=unique_object)
    except RecursionError as exc:
        raise ValueError('Experiment exceeds the supported nesting limit.') from exc
    return validate_json_tree(result)
