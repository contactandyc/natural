from dataclasses import dataclass, field
from decimal import Decimal
from datetime import date, datetime, timedelta
from target_orm import Myview

class SampleContext:
    def __init__(self):
        self.offset = 0
        self.name = ""
        self.lang = ""
    
def execute_sample(ctx: SampleContext, session):
    for record in session.query(Myview).filter((record.name >= 'SMITH')):
        ctx.offset = 2
        ctx.offset = 1
    return ctx

if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="Standalone runner for execute_sample")
    parser.add_argument("--offset", type=str, default=None, help="Initial value for --offset")
    parser.add_argument("--name", type=str, default=None, help="Initial value for --name")
    parser.add_argument("--lang", type=str, default=None, help="Initial value for --lang")
    args = parser.parse_args()
    ctx = SampleContext()
    
    if args.offset is not None:
        ctx.offset = int(args.offset)
    if args.name is not None:
        ctx.name = args.name
    if args.lang is not None:
        ctx.lang = args.lang
    
    class MockSession:
        def query(self, *args, **kwargs):
            return []
    
    session = MockSession()
    result = execute_sample(ctx, session)
    
    print(f"[execute_sample] Execution complete:")
    for k, v in sorted(result.__dict__.items()):
        if not k.startswith("_"):
            print(f"  {k}: {v}")