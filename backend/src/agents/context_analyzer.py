from langchain_core.prompts import ChatPromptTemplate


class ContextAnalyzerPrompt:

    @staticmethod
    def get_prompt():

        return """
        You are a Senior Business Analyst.

        Analyze the provided document.

        Extract:

        1. Problem Statement
        2. Business Goal
        3. Supporting Evidence
        4. Users
        5. Assumptions
        6. Constraints

        Return ONLY VALID JSON.

        Document:

        {document_text}
        """