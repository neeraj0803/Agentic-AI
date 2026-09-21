from ..graph.workflow import (
    build_graph
)


class ContextAnalyzerService:

    def __init__(self):

        self.graph = build_graph()

    def analyze(
        self,
        document_name: str,
        extracted_text: str
    ):

        state = {

            "document_name":
                document_name,

            "extracted_text":
                extracted_text
        }

        return self.graph.invoke(
            state
        )