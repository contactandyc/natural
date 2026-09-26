from dataclasses import dataclass, field
from decimal import Decimal
from datetime import date, datetime, timedelta

class Eom1Context:
    def __init__(self):
        self.date = date.today()
        self.datea = ""
    
    @property
    def yyyy(self) -> int:
        sub = self.datea[0:4]
        return int(sub) if sub.isdigit() else 0
    
    @yyyy.setter
    def yyyy(self, val: int):
        val_str = f'{int(val):04d}'
        self.datea = self.datea[:0] + val_str + self.datea[4:]
    
    @property
    def mm(self) -> int:
        sub = self.datea[4:6]
        return int(sub) if sub.isdigit() else 0
    
    @mm.setter
    def mm(self, val: int):
        val_str = f'{int(val):02d}'
        self.datea = self.datea[:4] + val_str + self.datea[6:]
    
    @property
    def dd(self) -> int:
        sub = self.datea[6:8]
        return int(sub) if sub.isdigit() else 0
    
    @dd.setter
    def dd(self, val: int):
        val_str = f'{int(val):02d}'
        self.datea = self.datea[:6] + val_str + self.datea[8:]
    
def execute_eom1(ctx: Eom1Context, session):
    ctx.date = (ctx.date + timedelta(days=31))
    ctx.datea = ctx.date.strftime('%Y%m%d')
    ctx.dd = 1
    ctx.date = datetime.strptime(ctx.datea, '%Y%m%d').date()
    ctx.date = (ctx.date - timedelta(days=1))
    return ctx

if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="Standalone runner for execute_eom1")
    parser.add_argument("--date", type=str, default=None, help="Initial value for --date")
    parser.add_argument("--datea", type=str, default=None, help="Initial value for --datea")
    args = parser.parse_args()
    ctx = Eom1Context()
    
    if args.date is not None:
        ctx.date = date.fromisoformat(args.date)
    if args.datea is not None:
        ctx.datea = args.datea
    
    class MockSession:
        def query(self, *args, **kwargs):
            return []
    
    session = MockSession()
    result = execute_eom1(ctx, session)
    
    print(f"[execute_eom1] Execution complete:")
    for k, v in sorted(result.__dict__.items()):
        if not k.startswith("_"):
            print(f"  {k}: {v}")
    print(f"  yyyy (redefine): {getattr(result, 'yyyy')}")
    print(f"  mm (redefine): {getattr(result, 'mm')}")
    print(f"  dd (redefine): {getattr(result, 'dd')}")