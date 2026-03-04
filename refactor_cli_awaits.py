import re

def main():
    with open("flow_engine/cli.py", "r") as f:
        code = f.read()

    # Replacements
    code = code.replace("app.repo.next_id()", "await app.repo.next_id()")
    code = code.replace("app.repo.load_all()", "await app.repo.load_all()")
    code = code.replace("app.repo.save_all(", "await app.repo.save_all(")
    code = code.replace("app.repo.get_active()", "await app.repo.get_active()")
    
    code = code.replace("app.engine.ensure_single_active(", "await app.engine.ensure_single_active(")
    code = code.replace("app.engine.transition(", "await app.engine.transition(")
    
    # Context
    code = code.replace("app.context.capture(", "await asyncio.to_thread(app.context.capture, ")
    code = code.replace("app.context.restore_latest(", "await asyncio.to_thread(app.context.restore_latest, ")

    # Git commit
    code = code.replace("app.vcs.commit(", "await asyncio.to_thread(app.vcs.commit, ")
    
    # Import asyncio if not present
    if "import asyncio" not in code:
        code = code.replace("import sys", "import sys\nimport asyncio")

    with open("flow_engine/cli.py", "w") as f:
        f.write(code)

if __name__ == "__main__":
    main()
