from src.services.prd_service import PRDGeneratorService

ctx = {
    "problem": "Employees struggle to find documents.",
    "users": ["Employees"],
    "needs": ["Find relevant docs quickly"],
    "expected_impact": ["Reduce search time"],
    "scope": {
        "in_scope": ["Search", "Retrieval"],
        "out_of_scope": ["Content authoring"],
    },
    "assumptions": ["Docs exist"],
    "constraints": ["No extra license"],
}

out = PRDGeneratorService().generate(ctx)
print("OK")
print(out.splitlines()[0])
import pathlib
print(pathlib.Path("prd_output.json").exists(), pathlib.Path("prd_output.md").exists())
