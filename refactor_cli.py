import re

def main():
    with open("flow_engine/cli.py", "r") as f:
        code = f.read()

    # Replace import
    code = code.replace("import click\n", "import asyncclick as click\n")

    # The commands to convert
    commands = [
        "main", "add", "ls", "start", "status", "done", "pause", 
        "block", "resume", "breakdown", "export", "templates", 
        "templates_ls", "plugins", "plugins_ls"
    ]

    for cmd in commands:
        code = re.sub(rf"^def {cmd}\(", rf"async def {cmd}(", code, flags=re.MULTILINE)

    # Change the entry point call
    code = code.replace('    main()', '    main(_anyio_backend="asyncio")')

    with open("flow_engine/cli.py", "w") as f:
        f.write(code)

if __name__ == "__main__":
    main()
