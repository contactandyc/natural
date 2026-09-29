from target_orm import Myview

class SampleContext:
    def __init__(self):
        self.offset = 0

def execute_sample(ctx: SampleContext, session):
    for loop_idx, record in enumerate(session.query(Myview).filter((Myview.name >= 'SMITH')), 1):
        loop_counter = loop_idx
        ctx.lang_UNRESOLVED[0][0] = '***'
        ctx.offset = 2
        session.flush()  # UPDATE committed for active loop
        ctx.offset = 1
    return ctx

if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="Standalone runner for execute_sample")
    parser.add_argument("--offset", dest="offset", type=str, default=None, help="Initial value for offset")
    args = parser.parse_args()
    ctx = SampleContext()

    if args.offset is not None:
        ctx.offset = int(args.offset)

    class MockQuery(list):
        def filter(self, *args, **kwargs):
            return self
        def limit(self, *args, **kwargs):
            return self
        def group_by(self, *args, **kwargs):
            return self

    class MockSession:
        def query(self, *args, **kwargs):
            return MockQuery()
        def add(self, obj): pass
        def delete(self, obj): pass
        def flush(self): pass
        def commit(self): pass
        def rollback(self): pass
        def refresh(self, obj): pass

    session = MockSession()
    result = execute_sample(ctx, session)

    print(f"[execute_sample] Execution complete:")
    for k, v in sorted(result.__dict__.items()):
        if not k.startswith("_"):
            print(f"  {k}: {v}")