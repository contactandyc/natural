from decimal import Decimal
from target_orm import Emp

class PaycalcContext:
    def __init__(self):
        self.input_id = ""
        self.bonus = Decimal('0')

def execute_paycalc(ctx: PaycalcContext, session):
    for loop_idx, record in enumerate(session.query(Emp).filter((Emp.name == ctx.input_id)), 1):
        loop_counter = loop_idx
        ctx.bonus = (record.salary * Decimal('0.10'))
        ctx.bonus = (ctx.bonus + Decimal('50.00'))
    return ctx

if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="Standalone runner for execute_paycalc")
    parser.add_argument("--input_id", type=str, default=None, help="Initial value for input_id")
    parser.add_argument("--bonus", type=str, default=None, help="Initial value for bonus")
    args = parser.parse_args()
    ctx = PaycalcContext()

    if args.input_id is not None:
        ctx.input_id = args.input_id
    if args.bonus is not None:
        ctx.bonus = Decimal(args.bonus)

    class MockQuery(list):
        def filter(self, *args, **kwargs):
            return self
        def limit(self, *args, **kwargs):
            return self

    class MockSession:
        def query(self, *args, **kwargs):
            return MockQuery()
        def add(self, obj): pass
        def delete(self, obj): pass
        def flush(self):
            pass

    session = MockSession()
    result = execute_paycalc(ctx, session)

    print(f"[execute_paycalc] Execution complete:")
    for k, v in sorted(result.__dict__.items()):
        if not k.startswith("_"):
            print(f"  {k}: {v}")