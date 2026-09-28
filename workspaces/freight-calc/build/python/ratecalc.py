from decimal import Decimal
from target_orm import Tariff

class RatecalcContext:
    def __init__(self):
        self.ship_class = ""
        self.route_zone = ""
        self.ship_weight = Decimal('0')
        self.final_charge = Decimal('0')
        self.base_charge = Decimal('0')
        self.surcharge = Decimal('0')

def execute_ratecalc(ctx: RatecalcContext, session):
    for loop_idx, record in enumerate(session.query(Tariff).filter((Tariff.class_ == ctx.ship_class)), 1):
        loop_counter = loop_idx
        ctx.base_charge = (record.rate * ctx.ship_weight)
        if (ctx.ship_weight > record.weight_limit):
            ctx.surcharge = record.heavy_surcharge
            break
    return ctx

if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="Standalone runner for execute_ratecalc")
    parser.add_argument("--ship-class", "--ship_class", dest="ship_class", type=str, default=None, help="Initial value for ship_class")
    parser.add_argument("--route-zone", "--route_zone", dest="route_zone", type=str, default=None, help="Initial value for route_zone")
    parser.add_argument("--ship-weight", "--ship_weight", dest="ship_weight", type=str, default=None, help="Initial value for ship_weight")
    parser.add_argument("--final-charge", "--final_charge", dest="final_charge", type=str, default=None, help="Initial value for final_charge")
    parser.add_argument("--base-charge", "--base_charge", dest="base_charge", type=str, default=None, help="Initial value for base_charge")
    parser.add_argument("--surcharge", dest="surcharge", type=str, default=None, help="Initial value for surcharge")
    args = parser.parse_args()
    ctx = RatecalcContext()

    if args.ship_class is not None:
        ctx.ship_class = args.ship_class
    if args.route_zone is not None:
        ctx.route_zone = args.route_zone
    if args.ship_weight is not None:
        ctx.ship_weight = Decimal(args.ship_weight)
    if args.final_charge is not None:
        ctx.final_charge = Decimal(args.final_charge)
    if args.base_charge is not None:
        ctx.base_charge = Decimal(args.base_charge)
    if args.surcharge is not None:
        ctx.surcharge = Decimal(args.surcharge)

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
    result = execute_ratecalc(ctx, session)

    print(f"[execute_ratecalc] Execution complete:")
    for k, v in sorted(result.__dict__.items()):
        if not k.startswith("_"):
            print(f"  {k}: {v}")