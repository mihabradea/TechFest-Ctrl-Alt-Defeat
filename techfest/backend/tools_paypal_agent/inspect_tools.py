# inspect_tools.py
from toolkit import toolkit

def main():
    tools = toolkit.get_tools()
    print("Tools available:", [t.name for t in tools])
    for t in tools:
        print("\n==", t.name, "==")
        # Most tools expose a JSON schema for inputs.
        schema = getattr(t, "input_schema", None) or getattr(t, "schema", None)
        print(schema)

if __name__ == "__main__":
    main()
