from .supabase_sync import push_all, push_phase5a

if __name__ == "__main__":
    import sys

    if "--phase5a-dry-run" in sys.argv:
        print(push_phase5a(dry_run=True))
    elif "--phase5a-upload" in sys.argv:
        # Explicit opt-in only; still requires env + prior migration.
        print(push_phase5a(dry_run=False))
    elif "--sync-only" in sys.argv:
        print(push_all())
    else:
        from .preload import start

        start(background=False)
