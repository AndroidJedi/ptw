#!/usr/bin/env python3
"""Explicit two-image capacity canary inside the existing bounded companion worker.

Runs only with PTW_PARALLEL_CANARY=1. Uses temporary outputs, no Project writes.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time


def main():
    if os.environ.get('PTW_PARALLEL_CANARY') != '1':
        raise RuntimeError('Explicit parallel canary environment is required')
    candidate, expected = Path(sys.argv[1]), sys.argv[2]
    if hashlib.sha256(candidate.read_bytes()).hexdigest() != expected:
        raise RuntimeError('Candidate worker digest mismatch')
    spec=importlib.util.spec_from_file_location('landing_candidate_worker',candidate)
    worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)
    from common.image_output import output_specification
    from common.database import database_url
    import psycopg
    with psycopg.connect(database_url(worker.secrets)) as db:
        if db.execute("SELECT count(*) FROM jobs WHERE status IN ('queued','running')").fetchone()[0]:
            raise RuntimeError('Wait for active companion jobs before the capacity canary')
    memory=Path('/sys/fs/cgroup/memory.current'); events=Path('/sys/fs/cgroup/memory.events')
    limit=int(Path('/sys/fs/cgroup/memory.max').read_text())
    before=events.read_text(); samples=[]; stopped=threading.Event()
    def sample():
        while not stopped.is_set():
            available=next(int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))
            samples.append((int(memory.read_text()),available)); stopped.wait(.5)
    sampler=threading.Thread(target=sample);sampler.start()
    try:
        with tempfile.TemporaryDirectory(prefix='ptw-parallel-canary-') as directory:
            os.environ['CONTENT_GRAPHIC_ASSET_DIR']=directory
            def generate(index):
                start=time.monotonic()
                result=worker.execute_structured_llm({
                    'mode':'content_non_human_graphic_generation','model':'gpt-6-astra',
                    'system_prompt':'Generate the requested polished hotel app screen, respecting the image output specification. Keep readable Ukrainian UI labels and generous whitespace.',
                    'input_payload':{'generation_policy_version':'ptw.domain-image.v1','output_spec':output_specification({'mode':'app_screen'}),
                        'operation':'image_generation','visual_direction':('A realistic hotel guest services app menu. Header Чим допомогти? Rows Переглянути послуги, Замовити послугу, Повідомити про проблему. Blue icons on a white background.' if index==0 else 'A realistic hotel guest service request screen. Header Замовити послугу. Options Прибирання номера, Заміна рушників, Доставка їжі. Blue primary button Замовити. White background.')},
                    'output_schema':{'type':'object','additionalProperties':False,'properties':{'generated':{'type':'boolean','const':True}},'required':['generated']}})
                return {'elapsed_ms':round((time.monotonic()-start)*1000),'sha256':result['image']['digest'],
                    'width':result['image']['width'],'height':result['image']['height'],'model':result['invocation']['model']}
            started=time.monotonic()
            with ThreadPoolExecutor(max_workers=2) as executor: results=list(executor.map(generate,range(2)))
            elapsed=round((time.monotonic()-started)*1000)
    finally:
        stopped.set();sampler.join()
    after=events.read_text()
    counts=lambda value: {line.split()[0]:int(line.split()[1]) for line in value.splitlines()}
    if any(counts(after)[key] != counts(before)[key] for key in ('oom','oom_kill')):
        raise RuntimeError('Memory OOM counter changed during parallel execution')
    peak=max(item[0] for item in samples);available=min(item[1] for item in samples)
    if peak > limit*.9 or available < 128*1024*1024:
        raise RuntimeError('Two-image execution lacks resource headroom')
    print(json.dumps({'jobs':results,'elapsed_ms':elapsed,'peak_worker_bytes':peak,'worker_limit_bytes':limit,'minimum_host_available_bytes':available,'oom_delta':0}),flush=True)


if __name__=='__main__':
    try: main()
    except Exception as error:
        print(json.dumps({'status':'failed','category':type(error).__name__}),flush=True)
        raise SystemExit(1)
