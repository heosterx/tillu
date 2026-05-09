"""
Research Agent - LangGraph StateGraph Implementation

7-Node Directed Graph with retry loops:
PLAN → SEARCH → SCRAPE → EXTRACT → SYNTHESIZE → CRITIQUE → STORE

Uses Cerebras for synthesis, Groq for planning/critique
"""
from typing import TypedDict, List, Dict, Any, Optional, Annotated
from datetime import datetime
import operator
import time

from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from langchain_cerebras import ChatCerebras
from langchain.prompts import ChatPromptTemplate
from langchain.schema import SystemMessage, HumanMessage

from app.config import settings
from app.utils.logging import get_logger
from app.utils.database import db
from app.transformers.embeddings import embedding_generator
from app.tools.search_tools import WebSearchTool, BraveSearchTool
from app.transformers.extractors import NERExtractor, Summarizer

logger = get_logger("research_agent")


class ResearchState(TypedDict):
    """State for research agent"""
    task: str
    user_id: str
    research_plan: Dict[str, Any]
    search_results: List[Dict[str, Any]]
    scraped_content: List[Dict[str, Any]]
    extracted_entities: List[Dict[str, Any]]
    synthesis: str
    critique: Dict[str, Any]
    iteration_count: int
    status: str
    max_iterations: int
    session_id: Optional[str]


class ResearchAgent:
    """
    LangGraph Research Agent
    7-node state machine for deep research tasks
    """
    
    def __init__(self):
        self.logger = get_logger("research_agent")
        self.workflow = self._build_workflow()
        
        # Initialize LLMs
        self.planning_llm = ChatGroq(
            api_key=settings.groq_api_key,
            model_name="llama-3.1-8b-instant",
            temperature=0.7
        ) if settings.groq_api_key else None
        
        self.synthesis_llm = ChatCerebras(
            api_key=settings.cerebras_api_key,
            model_name="llama-3.3-70b",
            temperature=0.6
        ) if settings.cerebras_api_key else None
        
        self.critique_llm = ChatGroq(
            api_key=settings.groq_api_key,
            model_name="llama-3.1-8b-instant",
            temperature=0.5
        ) if settings.groq_api_key else None
        
        # Tools
        self.web_search = WebSearchTool()
        self.brave_search = BraveSearchTool()
        self.ner = NERExtractor()
        self.summarizer = Summarizer()
    
    def _build_workflow(self) -> StateGraph:
        """Build the 7-node research workflow"""
        
        workflow = StateGraph(ResearchState)
        
        # Add nodes
        workflow.add_node("plan", self._plan_node)
        workflow.add_node("search", self._search_node)
        workflow.add_node("scrape", self._scrape_node)
        workflow.add_node("extract", self._extract_node)
        workflow.add_node("synthesize", self._synthesize_node)
        workflow.add_node("critique", self._critique_node)
        workflow.add_node("store", self._store_node)
        
        # Add edges
        workflow.set_entry_point("plan")
        workflow.add_edge("plan", "search")
        workflow.add_edge("search", "scrape")
        workflow.add_edge("scrape", "extract")
        workflow.add_edge("extract", "synthesize")
        workflow.add_edge("synthesize", "critique")
        
        # Conditional edge from critique
        workflow.add_conditional_edges(
            "critique",
            self._critique_router,
            {
                "search_again": "search",
                "store": "store",
                "max_iterations": "store"
            }
        )
        
        workflow.add_edge("store", END)
        
        return workflow.compile()
    
    async def _plan_node(self, state: ResearchState) -> ResearchState:
        """
        PLAN NODE
        → LLM decomposes topic into research angles
        → Identifies optimal sources per angle
        """
        self.logger.info("Research: Planning phase", task=state["task"])
        
        if not self.planning_llm:
            # Fallback plan
            state["research_plan"] = {
                "angles": ["general overview", "recent developments", "expert opinions"],
                "sources": ["web", "news"],
                "estimated_steps": 3
            }
            return state
        
        try:
            prompt = f"""You are a research planner. Break down the following research task into specific angles and identify the best sources for each.

Task: {state["task"]}

Output a JSON-like structure with:
- angles: list of 3-5 specific research angles
- sources: recommended sources for each angle (web, academic, news, etc.)
- key_questions: specific questions to answer

Be concise and specific."""

            response = await self.planning_llm.ainvoke([HumanMessage(content=prompt)])
            
            # Parse plan from response
            plan_text = response.content
            
            state["research_plan"] = {
                "raw_plan": plan_text,
                "angles": self._extract_angles(plan_text),
                "sources": ["web", "news", "academic"],
                "estimated_steps": 3
            }
            
        except Exception as e:
            self.logger.error(f"Planning error: {e}")
            state["research_plan"] = {
                "angles": [state["task"]],
                "sources": ["web"],
                "error": str(e)
            }
        
        state["status"] = "planning_complete"
        return state
    
    def _extract_angles(self, plan_text: str) -> List[str]:
        """Extract research angles from plan text"""
        import re
        angles = []
        
        # Look for numbered lists or bullet points
        lines = plan_text.split('\n')
        for line in lines:
            # Match patterns like "1. angle" or "- angle" or "* angle"
            match = re.match(r'^[\s]*[\d\-\*\.]\s*[\.)]?\s*(.+)', line)
            if match:
                angles.append(match.group(1).strip())
        
        if not angles:
            angles = [plan_text[:100]]  # Fallback
        
        return angles[:5]  # Max 5 angles
    
    async def _search_node(self, state: ResearchState) -> ResearchState:
        """
        SEARCH NODE (parallel)
        → SearXNG: meta-search across all engines
        → ArXiv: academic papers
        → GitHub: technical repositories
        → Reddit: community perspectives
        """
        self.logger.info("Research: Search phase", angles=state["research_plan"].get("angles", []))
        
        search_results = []
        
        # Search for each angle
        for angle in state["research_plan"].get("angles", [state["task"]])[:3]:
            try:
                # Web search via SearXNG
                web_result = await self.web_search.execute(
                    query=angle,
                    num_results=5
                )
                
                if web_result.get("success"):
                    for r in web_result.get("results", []):
                        search_results.append({
                            "url": r.get("url"),
                            "title": r.get("title"),
                            "snippet": r.get("content", ""),
                            "source": "web",
                            "angle": angle
                        })
                
                # Brave search for diversity
                brave_result = await self.brave_search.execute(
                    query=angle,
                    num_results=3
                )
                
                if brave_result.get("success"):
                    for r in brave_result.get("results", []):
                        search_results.append({
                            "url": r.get("url"),
                            "title": r.get("title"),
                            "snippet": r.get("description", ""),
                            "source": "brave",
                            "angle": angle
                        })
                        
            except Exception as e:
                self.logger.error(f"Search error for angle {angle}: {e}")
        
        # Deduplicate by URL
        seen_urls = set()
        unique_results = []
        for r in search_results:
            if r["url"] and r["url"] not in seen_urls:
                seen_urls.add(r["url"])
                unique_results.append(r)
        
        state["search_results"] = unique_results[:15]  # Top 15
        state["status"] = "search_complete"
        
        self.logger.info(f"Found {len(unique_results)} unique results")
        return state
    
    async def _scrape_node(self, state: ResearchState) -> ResearchState:
        """
        SCRAPE NODE
        → Playwright renders each URL
        → BART summarizes each page (100-200 words)
        """
        self.logger.info("Research: Scraping phase", urls=len(state["search_results"]))
        
        scraped = []
        
        # Scrape top results (limit to avoid timeouts)
        for result in state["search_results"][:8]:
            try:
                url = result.get("url")
                if not url:
                    continue
                
                # For now, use the snippet as content
                # In production, use Playwright to render
                content = result.get("snippet", "")
                
                # Summarize if content is long
                if len(content) > 300:
                    summary = await self.summarizer.summarize(
                        content,
                        max_length=200,
                        min_length=50
                    )
                else:
                    summary = content
                
                scraped.append({
                    "url": url,
                    "title": result.get("title"),
                    "summary": summary,
                    "source": result.get("source"),
                    "angle": result.get("angle"),
                    "word_count": len(summary.split())
                })
                
            except Exception as e:
                self.logger.error(f"Scrape error for {result.get('url')}: {e}")
        
        state["scraped_content"] = scraped
        state["status"] = "scrape_complete"
        
        self.logger.info(f"Scraped {len(scraped)} pages")
        return state
    
    async def _extract_node(self, state: ResearchState) -> ResearchState:
        """
        EXTRACT NODE
        → NER extracts entities (people, orgs, stats, dates)
        """
        self.logger.info("Research: Extraction phase")
        
        all_entities = []
        
        # Extract from all summaries
        for content in state["scraped_content"]:
            try:
                text = content.get("summary", "")
                if len(text) > 50:
                    entities = await self.ner.extract(text)
                    for e in entities:
                        e["source_url"] = content.get("url")
                    all_entities.extend(entities)
            except Exception as e:
                self.logger.error(f"NER error: {e}")
        
        # Deduplicate entities
        seen = set()
        unique_entities = []
        for e in all_entities:
            key = f"{e.get('word', '').lower()}:{e.get('type', '')}"
            if key not in seen and e.get('score', 0) > 0.7:
                seen.add(key)
                unique_entities.append(e)
        
        state["extracted_entities"] = unique_entities[:20]  # Top 20
        state["status"] = "extract_complete"
        
        return state
    
    async def _synthesize_node(self, state: ResearchState) -> ResearchState:
        """
        SYNTHESIZE NODE
        → All summaries → Cerebras 70B
        → Structured synthesis with citations
        """
        self.logger.info("Research: Synthesis phase")
        
        if not self.synthesis_llm:
            # Fallback synthesis
            summaries = [c.get("summary", "") for c in state["scraped_content"]]
            state["synthesis"] = "\n\n".join(summaries[:3])
            return state
        
        try:
            # Build context from scraped content
            context_parts = []
            for i, content in enumerate(state["scraped_content"][:6], 1):
                context_parts.append(
                    f"[{i}] {content.get('title', 'Untitled')}\n"
                    f"Source: {content.get('url', 'Unknown')}\n"
                    f"Summary: {content.get('summary', '')[:300]}\n"
                )
            
            context = "\n".join(context_parts)
            
            # Build entities list
            entities_text = "\n".join([
                f"- {e.get('word')} ({e.get('type')})"
                for e in state["extracted_entities"][:10]
            ])
            
            prompt = f"""Synthesize the following research findings into a comprehensive analysis.

Research Task: {state["task"]}

Sources:
{context}

Key Entities Found:
{entities_text}

Provide a structured synthesis with:
1. Executive Summary (3-4 sentences)
2. Key Findings (bullet points with citations [1], [2], etc.)
3. Important Entities (people, organizations, dates mentioned)
4. Contradictions or gaps in sources
5. Conclusion

Be thorough but concise."""

            response = await self.synthesis_llm.ainvoke([HumanMessage(content=prompt)])
            state["synthesis"] = response.content
            
        except Exception as e:
            self.logger.error(f"Synthesis error: {e}")
            state["synthesis"] = f"Error during synthesis: {str(e)}"
        
        state["status"] = "synthesis_complete"
        return state
    
    async def _critique_node(self, state: ResearchState) -> ResearchState:
        """
        CRITIQUE NODE
        → Groq 8B evaluates synthesis depth
        → If shallow → back to SEARCH NODE (max 3 iterations)
        → If sufficient → STORE NODE
        """
        self.logger.info("Research: Critique phase", iteration=state["iteration_count"])
        
        critique_result = {
            "depth_score": 0.7,
            "needs_more_research": False,
            "feedback": ""
        }
        
        if not self.critique_llm:
            state["critique"] = critique_result
            return state
        
        try:
            prompt = f"""Critique the following research synthesis. Evaluate:
1. Depth (1-10): Does it cover the topic thoroughly?
2. Accuracy: Are claims supported by sources?
3. Completeness: Are there obvious gaps?

Synthesis:
{state["synthesis"][:1500]}  # Truncate for token limit

Respond in this format:
Depth Score: [1-10]
Needs More Research: [Yes/No]
Feedback: [Specific suggestions for improvement]"""

            response = await self.critique_llm.ainvoke([HumanMessage(content=prompt)])
            critique_text = response.content
            
            # Parse critique
            critique_result = self._parse_critique(critique_text)
            
        except Exception as e:
            self.logger.error(f"Critique error: {e}")
            critique_result["feedback"] = f"Error: {str(e)}"
        
        state["critique"] = critique_result
        state["iteration_count"] = state.get("iteration_count", 0) + 1
        
        return state
    
    def _parse_critique(self, text: str) -> Dict[str, Any]:
        """Parse critique response"""
        result = {
            "depth_score": 7,
            "needs_more_research": False,
            "feedback": text
        }
        
        import re
        
        # Extract depth score
        score_match = re.search(r'Depth Score:\s*(\d+)', text)
        if score_match:
            result["depth_score"] = int(score_match.group(1))
        
        # Check if needs more research
        if "Yes" in text and "Needs More Research" in text:
            result["needs_more_research"] = True
        
        return result
    
    def _critique_router(self, state: ResearchState) -> str:
        """Route based on critique results"""
        iteration = state.get("iteration_count", 0)
        max_iterations = state.get("max_iterations", 3)
        critique = state.get("critique", {})
        
        # Max iterations reached
        if iteration >= max_iterations:
            self.logger.info(f"Max iterations ({max_iterations}) reached, storing")
            return "max_iterations"
        
        # Needs more research and depth is low
        if critique.get("needs_more_research") and critique.get("depth_score", 7) < 6:
            self.logger.info(f"Iteration {iteration}: Needs more research")
            return "search_again"
        
        # Sufficient quality
        self.logger.info(f"Iteration {iteration}: Synthesis sufficient")
        return "store"
    
    async def _store_node(self, state: ResearchState) -> ResearchState:
        """
        STORE NODE
        → Full research → Supabase research_sessions
        → Embeddings generated → pgvector
        → Summary → knowledge_base
        """
        self.logger.info("Research: Storing results")
        
        try:
            # Create research session record
            research_data = {
                "user_id": state["user_id"],
                "query": state["task"],
                "research_plan": state["research_plan"],
                "search_results": state["search_results"],
                "scraped_content": state["scraped_content"],
                "synthesis": state["synthesis"],
                "critique": state["critique"],
                "iteration_count": state.get("iteration_count", 1),
                "executive_summary": self._extract_executive_summary(state["synthesis"]),
                "citations": [{"url": c.get("url"), "title": c.get("title")} 
                             for c in state["scraped_content"][:5]],
                "status": "complete"
            }
            
            # Generate embedding for the synthesis
            embedding = await embedding_generator.generate(
                state["synthesis"][:1000]  # First 1000 chars for embedding
            )
            if embedding:
                research_data["embedding"] = embedding
            
            # Store in database
            result = await db.insert("research_sessions", research_data)
            
            if result:
                self.logger.info(f"Research stored: {result[0]['id']}")
                state["research_id"] = result[0]["id"]
            
        except Exception as e:
            self.logger.error(f"Store error: {e}")
        
        state["status"] = "complete"
        return state
    
    def _extract_executive_summary(self, synthesis: str) -> str:
        """Extract executive summary from synthesis"""
        lines = synthesis.split('\n')
        
        # Look for executive summary section
        in_summary = False
        summary_lines = []
        
        for line in lines:
            if 'executive summary' in line.lower() or 'summary' in line.lower():
                in_summary = True
                continue
            
            if in_summary:
                if line.strip() and not line.startswith('#'):
                    summary_lines.append(line.strip())
                elif len(summary_lines) > 3:
                    break
        
        if summary_lines:
            return ' '.join(summary_lines[:4])
        
        # Fallback: first paragraph
        return ' '.join(lines[:3])[:500]
    
    async def execute(self, task: str, user_id: str) -> Dict[str, Any]:
        """
        Execute full research workflow
        
        Args:
            task: Research query/topic
            user_id: User ID
            
        Returns:
            Research results
        """
        start_time = time.time()
        
        # Initialize state
        initial_state = {
            "task": task,
            "user_id": user_id,
            "research_plan": {},
            "search_results": [],
            "scraped_content": [],
            "extracted_entities": [],
            "synthesis": "",
            "critique": {},
            "iteration_count": 0,
            "status": "started",
            "max_iterations": 3
        }
        
        # Run workflow
        try:
            result = await self.workflow.ainvoke(initial_state)
            
            elapsed = time.time() - start_time
            
            return {
                "success": True,
                "query": task,
                "synthesis": result.get("synthesis"),
                "executive_summary": result.get("synthesis", "")[:500],
                "sources": [{"url": c.get("url"), "title": c.get("title")} 
                           for c in result.get("scraped_content", [])],
                "entities": result.get("extracted_entities", []),
                "iterations": result.get("iteration_count", 1),
                "research_id": result.get("research_id"),
                "elapsed_seconds": elapsed,
                "status": result.get("status")
            }
            
        except Exception as e:
            self.logger.error(f"Research workflow error: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": task
            }


def create_research_agent() -> ResearchAgent:
    """Factory function to create research agent"""
    return ResearchAgent()
