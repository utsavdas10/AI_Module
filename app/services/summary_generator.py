import logging
import json
from typing import List, Dict, Any

# Local application imports
from app.prompts.query_prompt import get_query_prompt

# Gemini Client
# import google.generativeai as genai

logger = logging.getLogger(__name__)

class SummaryGenerator:

    # This method generates insights and visualizations based on the query result.
    async def analyze(self, model, original_question: str, query_result: List[Dict[str, Any]]) -> Dict[str, Any]:
        # Generate the detailed analysis using the LLM for deep interpretation
        detailed_analysis = await self._generate_detailed_analysis(model, original_question, query_result)

        # If the analysis looks like a JSON code block, extract and parse it
        if isinstance(detailed_analysis, str) and detailed_analysis.strip().startswith('```json'):
            cleaned = detailed_analysis.strip()
            if cleaned.startswith('```json'):
                cleaned = cleaned[len('```json'):]
            if cleaned.endswith('```'):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            try:
                detailed_analysis = json.loads(cleaned)
            except Exception as e:
                logger.error(f"Failed to parse JSON from LLM analysis: {e}")

        return {"detailed_analysis": detailed_analysis,}




    # This method generates a detailed analysis of the query result using the Gemini LLM.
    async def _generate_detailed_analysis(self, model, question: str, data: List[Dict[str, Any]]) -> str:

        num_rows = len(data)

        if num_rows == 0:
            return "Based on the available data, I could not find any information to answer your question. The query returned no results."

        preview_limit = num_rows if num_rows < 5000 else 5000  # Allow a larger preview for analysis
        data_preview_str = json.dumps(data[:preview_limit], indent=2, default=str)

        prompt = get_query_prompt(question, data_preview_str)

        try:
            response = await model.generate_content_async(prompt)
            analysis = response.text.strip()
            return analysis
        except Exception as e:
            logger.error(f"Failed to generate detailed analysis from Gemini: {e}")
            return f"The query to support your analysis returned {num_rows} result(s). A detailed analysis could not be generated at this time."

