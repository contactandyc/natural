from dataclasses import dataclass, field
from decimal import Decimal
from datetime import date, datetime, timedelta

class Eom2Context:
    def __init__(self):
        self.date = date.today()
        self.t = ""
        self.d = date.today()
    
    @property
    def dd(self) -> int:
        sub = self.t[0:2]
        return int(sub) if sub.isdigit() else 0
    
    @dd.setter
    def dd(self, val: int):
        val_str = f'{int(val):02d}'
        self.t = self.t[:0] + val_str + self.t[2:]
    
def execute_eom2(ctx: Eom2Context, session):
    ctx.t = ctx.date.strftime('%d%m%Y')
    if (ctx.dd < 28):
        ctx.dd = 28
    while not ((ctx.dd == 1)):
        ctx.d = datetime.strptime(ctx.t, '%d%m%Y').date()
        ctx.d = (ctx.d + timedelta(days=1))
        ctx.t = ctx.d.strftime('%d%m%Y')
    ctx.d = (ctx.d - timedelta(days=1))
    return ctx

if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="Standalone runner for execute_eom2")
    parser.add_argument("--date", type=str, default=None, help="Initial value for --date")
    parser.add_argument("--t", type=str, default=None, help="Initial value for --t")
    parser.add_argument("--d", type=str, default=None, help="Initial value for --d")
    args = parser.parse_args()
    ctx = Eom2Context()
    
    if args.date is not None:
        ctx.date = date.fromisoformat(args.date)
    if args.t is not None:
        ctx.t = args.t
    if args.d is not None:
        ctx.d = date.fromisoformat(args.d)
    
    class MockSession:
        def query(self, *args, **kwargs):
            return []
    
    session = MockSession()
    result = execute_eom2(ctx, session)
    
    print(f"[execute_eom2] Execution complete:")
    for k, v in sorted(result.__dict__.items()):
        if not k.startswith("_"):
            print(f"  {k}: {v}")
    print(f"  dd (redefine): {getattr(result, 'dd')}")