from .supabase_sync import push_all

if __name__ == "__main__":
    import os
    import sys

    if "--sync-only" in sys.argv:
        print(push_all())
    else:
        from .preload import start

        start(background=False)

