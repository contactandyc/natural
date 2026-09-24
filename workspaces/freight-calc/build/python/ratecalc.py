from dataclasses import dataclass
from decimal import Decimal
from target_orm import Tariff

@dataclass
class RatecalcContext:
    ship_class: str
    route_zone: str
    ship_weight: Decimal
    final_charge: Decimal
    base_charge: Decimal = Decimal('0')
    surcharge: Decimal = Decimal('0')

def execute_ratecalc(ctx: RatecalcContext, session):
    for record in session.query(Tariff).filter((record.class_ == ctx.ship_class)):
        ctx.base_charge = (record.rate * ctx.ship_weight)
        if (ctx.ship_weight > record.weight_limit):
            ctx.surcharge = record.heavy_surcharge
            break
    return ctx