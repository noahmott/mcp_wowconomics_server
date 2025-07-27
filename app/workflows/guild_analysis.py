"""
LangGraph Workflow for Guild Analysis
"""

import os
import logging
from typing import Dict, Any, List, TypedDict, Annotated
from datetime import datetime
import asyncio

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import StateGraph, END, START
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
import json

from ..utils.wow_utils import get_localized_name, parse_class_info, parse_realm_info

logger = logging.getLogger(__name__)


class GuildAnalysisState(TypedDict):
    """State for guild analysis workflow"""
    messages: Annotated[list, add_messages]
    guild_info: dict
    member_data: list
    analysis_results: dict
    visualization_urls: list
    error_context: dict
    user_preferences: dict
    classification_result: str
    analysis_type: str


class GuildAnalysisWorkflow:
    """LangGraph workflow for comprehensive guild analysis"""
    
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            self.llm = ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0,
                api_key=api_key
            )
        else:
            self.llm = None
            logger.warning("OpenAI API key not provided - AI insights will be disabled")
        
        # Build the workflow graph
        self.workflow = self._build_workflow()
        
        # Compile with memory saver
        memory = MemorySaver()
        self.app = self.workflow.compile(checkpointer=memory)
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow"""
        workflow = StateGraph(GuildAnalysisState)
        
        # Add nodes
        workflow.add_node("classify_request", self._classify_request)
        workflow.add_node("analyze_guild_overview", self._analyze_guild_overview)
        workflow.add_node("analyze_member_performance", self._analyze_member_performance)
        workflow.add_node("analyze_raid_progress", self._analyze_raid_progress)
        workflow.add_node("generate_insights", self._generate_insights)
        workflow.add_node("format_response", self._format_response)
        workflow.add_node("handle_error", self._handle_error)
        
        # Add edges
        workflow.add_edge(START, "classify_request")
        
        # Conditional routing based on classification
        workflow.add_conditional_edges(
            "classify_request",
            self._route_analysis,
            {
                "guild_overview": "analyze_guild_overview",
                "member_analysis": "analyze_member_performance",
                "raid_progress": "analyze_raid_progress",
                "error": "handle_error"
            }
        )
        
        # All analysis nodes lead to insights generation
        workflow.add_edge("analyze_guild_overview", "generate_insights")
        workflow.add_edge("analyze_member_performance", "generate_insights")
        workflow.add_edge("analyze_raid_progress", "generate_insights")
        
        # Generate insights leads to formatting
        workflow.add_edge("generate_insights", "format_response")
        workflow.add_edge("format_response", END)
        workflow.add_edge("handle_error", END)
        
        return workflow
    
    async def analyze_guild(self, guild_data: Dict[str, Any], analysis_type: str = "comprehensive") -> Dict[str, Any]:
        """
        Analyze guild data using LangGraph workflow
        
        Args:
            guild_data: Guild data from Blizzard API
            analysis_type: Type of analysis to perform
        
        Returns:
            Analysis results
        """
        try:
            # Initialize state
            initial_state = GuildAnalysisState(
                messages=[HumanMessage(content=f"Analyze guild with type: {analysis_type}")],
                guild_info=guild_data.get("guild_info", {}),
                member_data=guild_data.get("members_data", []),
                analysis_results={},
                visualization_urls=[],
                error_context={},
                user_preferences={},
                classification_result="",
                analysis_type=analysis_type
            )
            
            # Run the workflow
            config = {"configurable": {"thread_id": f"guild_analysis_{datetime.now().timestamp()}"}}
            result = await self.app.ainvoke(initial_state, config)
            
            return result
            
        except Exception as e:
            logger.error(f"Error in guild analysis workflow: {str(e)}")
            return {
                "guild_summary": {"error": f"Analysis failed: {str(e)}"},
                "member_analysis": [],
                "performance_insights": {"error": str(e)},
                "chart_urls": []
            }
    
    async def analyze_member(self, member_data: Dict[str, Any], analysis_depth: str = "standard") -> Dict[str, Any]:
        """
        Analyze individual member data
        
        Args:
            member_data: Member data from Blizzard API
            analysis_depth: Depth of analysis
        
        Returns:
            Member analysis results
        """
        try:
            # Simple member analysis without full workflow
            character_summary = self._summarize_character(member_data)
            performance_analysis = self._analyze_character_performance(member_data)
            equipment_insights = self._analyze_equipment(member_data)
            
            return {
                "character_summary": character_summary,
                "performance_analysis": performance_analysis,
                "equipment_insights": equipment_insights,
                "progression_summary": self._analyze_progression(member_data)
            }
            
        except Exception as e:
            logger.error(f"Error in member analysis: {str(e)}")
            return {
                "character_summary": {"error": f"Member analysis failed: {str(e)}"},
                "performance_analysis": {},
                "equipment_insights": {},
                "progression_summary": {}
            }
    
    async def _classify_request(self, state: GuildAnalysisState) -> GuildAnalysisState:
        """Classify the analysis request"""
        try:
            analysis_type = state.get("analysis_type", "comprehensive")
            
            # Simple classification based on analysis type
            if analysis_type in ["comprehensive", "basic"]:
                classification = "guild_overview"
            elif analysis_type == "performance":
                classification = "member_analysis"
            elif analysis_type == "raids":
                classification = "raid_progress"
            else:
                classification = "guild_overview"
            
            state["classification_result"] = classification
            
            logger.info(f"Classified request as: {classification}")
            return state
            
        except Exception as e:
            logger.error(f"Error in classification: {str(e)}")
            state["error_context"] = {"type": "classification_error", "message": str(e)}
            state["classification_result"] = "error"
            return state
    
    async def _analyze_guild_overview(self, state: GuildAnalysisState) -> GuildAnalysisState:
        """Analyze guild overview"""
        try:
            guild_info = state["guild_info"]
            member_data = state["member_data"]
            
            # Basic guild statistics
            realm_info = parse_realm_info(guild_info.get("realm"))
            guild_summary = {
                "name": get_localized_name(guild_info),
                "realm": realm_info["name"],
                "faction": get_localized_name(guild_info, "faction"),
                "member_count": guild_info.get("member_count", len(member_data)),
                "achievement_points": guild_info.get("achievement_points", 0),
                "created_timestamp": guild_info.get("created_timestamp")
            }
            
            # Member statistics
            if member_data:
                levels = [m.get("level", 0) for m in member_data if m.get("level")]
                item_levels = []
                
                for member in member_data:
                    eq = member.get("equipment_summary", {})
                    if eq.get("average_item_level"):
                        item_levels.append(eq["average_item_level"])
                
                member_stats = {
                    "total_members": len(member_data),
                    "max_level_members": len([l for l in levels if l >= 80]),
                    "average_level": sum(levels) / len(levels) if levels else 0,
                    "average_item_level": sum(item_levels) / len(item_levels) if item_levels else 0,
                    "class_distribution": self._get_class_distribution(member_data)
                }
            else:
                member_stats = {"total_members": 0}
            
            state["analysis_results"]["guild_overview"] = {
                "guild_summary": guild_summary,
                "member_statistics": member_stats
            }
            
            logger.info("Completed guild overview analysis")
            return state
            
        except Exception as e:
            logger.error(f"Error in guild overview analysis: {str(e)}")
            state["error_context"] = {"type": "analysis_error", "message": str(e)}
            return state
    
    async def _analyze_member_performance(self, state: GuildAnalysisState) -> GuildAnalysisState:
        """Analyze member performance"""
        try:
            member_data = state["member_data"]
            
            if not member_data:
                state["analysis_results"]["member_performance"] = {"error": "No member data available"}
                return state
            
            # Analyze top performers
            top_performers = self._identify_top_performers(member_data)
            
            # Performance distribution
            performance_dist = self._analyze_performance_distribution(member_data)
            
            state["analysis_results"]["member_performance"] = {
                "top_performers": top_performers,
                "performance_distribution": performance_dist,
                "total_analyzed": len(member_data)
            }
            
            logger.info("Completed member performance analysis")
            return state
            
        except Exception as e:
            logger.error(f"Error in member performance analysis: {str(e)}")
            state["error_context"] = {"type": "analysis_error", "message": str(e)}
            return state
    
    async def _analyze_raid_progress(self, state: GuildAnalysisState) -> GuildAnalysisState:
        """Analyze raid progression"""
        try:
            guild_info = state["guild_info"]
            
            # Mock raid analysis - would integrate with actual achievement data
            raid_analysis = {
                "current_progress": {
                    "raid_name": "Amirdrassil, the Dream's Hope",
                    "difficulties": {
                        "Normal": {"completed": True, "progress": "9/9"},
                        "Heroic": {"completed": False, "progress": "4/9"},
                        "Mythic": {"completed": False, "progress": "1/9"}
                    }
                },
                "progression_insights": [
                    "Guild has strong Normal mode progression",
                    "Heroic progression in progress",
                    "Recently started Mythic difficulty"
                ]
            }
            
            state["analysis_results"]["raid_progress"] = raid_analysis
            
            logger.info("Completed raid progress analysis")
            return state
            
        except Exception as e:
            logger.error(f"Error in raid progress analysis: {str(e)}")
            state["error_context"] = {"type": "analysis_error", "message": str(e)}
            return state
    
    async def _generate_insights(self, state: GuildAnalysisState) -> GuildAnalysisState:
        """Generate AI-powered insights"""
        try:
            analysis_results = state["analysis_results"]
            
            # Create insight prompt
            prompt = f"""
            Based on the following WoW guild analysis data, provide meaningful insights and recommendations:
            
            Analysis Results: {json.dumps(analysis_results, indent=2)}
            
            Please provide:
            1. Key strengths of the guild
            2. Areas for improvement
            3. Specific recommendations
            4. Notable trends or patterns
            
            Keep insights concise and actionable.
            """
            
            # Generate insights using LLM if available
            if self.llm:
                response = await self.llm.ainvoke([HumanMessage(content=prompt)])
                ai_insights_text = response.content
            else:
                ai_insights_text = "AI insights unavailable - OpenAI API key not configured"
            
            insights = {
                "ai_insights": ai_insights_text,
                "generated_at": datetime.now().isoformat(),
                "key_metrics": self._extract_key_metrics(analysis_results)
            }
            
            state["analysis_results"]["insights"] = insights
            
            logger.info("Generated AI insights")
            return state
            
        except Exception as e:
            logger.error(f"Error generating insights: {str(e)}")
            state["analysis_results"]["insights"] = {"error": f"Failed to generate insights: {str(e)}"}
            return state
    
    async def _format_response(self, state: GuildAnalysisState) -> GuildAnalysisState:
        """Format final response"""
        try:
            analysis_results = state["analysis_results"]
            
            # Format for external consumption
            formatted_response = {
                "guild_summary": analysis_results.get("guild_overview", {}).get("guild_summary", {}),
                "member_analysis": analysis_results.get("member_performance", {}),
                "performance_insights": analysis_results.get("insights", {}),
                "chart_urls": state.get("visualization_urls", []),
                "analysis_timestamp": datetime.now().isoformat()
            }
            
            state["analysis_results"]["formatted_response"] = formatted_response
            
            logger.info("Formatted analysis response")
            return state
            
        except Exception as e:
            logger.error(f"Error formatting response: {str(e)}")
            state["error_context"] = {"type": "formatting_error", "message": str(e)}
            return state
    
    async def _handle_error(self, state: GuildAnalysisState) -> GuildAnalysisState:
        """Handle errors in the workflow"""
        error_context = state.get("error_context", {})
        error_type = error_context.get("type", "unknown")
        error_message = error_context.get("message", "Unknown error occurred")
        
        logger.error(f"Workflow error: {error_type} - {error_message}")
        
        # Provide helpful error response
        state["analysis_results"] = {
            "error": True,
            "error_type": error_type,
            "error_message": error_message,
            "suggestions": self._get_error_suggestions(error_type)
        }
        
        return state
    
    def _route_analysis(self, state: GuildAnalysisState) -> str:
        """Route to appropriate analysis based on classification"""
        classification = state.get("classification_result", "guild_overview")
        return classification
    
    def _get_class_distribution(self, member_data: List[Dict[str, Any]]) -> Dict[str, int]:
        """Get class distribution from member data"""
        distribution = {}
        for member in member_data:
            class_name = parse_class_info(member.get("character_class"))
            distribution[class_name] = distribution.get(class_name, 0) + 1
        return distribution
    
    def _identify_top_performers(self, member_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify top performing members"""
        performers = []
        
        for member in member_data:
            eq_summary = member.get("equipment_summary", {})
            if eq_summary.get("average_item_level", 0) > 450:  # High item level threshold
                performers.append({
                    "name": get_localized_name(member),
                    "item_level": eq_summary.get("average_item_level", 0),
                    "level": member.get("level", 0),
                    "class": parse_class_info(member.get("character_class"))
                })
        
        # Sort by item level
        performers.sort(key=lambda x: x["item_level"], reverse=True)
        return performers[:10]  # Top 10
    
    def _analyze_performance_distribution(self, member_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze performance distribution"""
        item_levels = []
        levels = []
        
        for member in member_data:
            eq = member.get("equipment_summary", {})
            if eq.get("average_item_level"):
                item_levels.append(eq["average_item_level"])
            
            if member.get("level"):
                levels.append(member.get("level"))
        
        return {
            "item_level_stats": {
                "average": sum(item_levels) / len(item_levels) if item_levels else 0,
                "max": max(item_levels) if item_levels else 0,
                "min": min(item_levels) if item_levels else 0
            },
            "level_stats": {
                "average": sum(levels) / len(levels) if levels else 0,
                "max": max(levels) if levels else 0,
                "max_level_count": len([l for l in levels if l >= 80])
            }
        }
    
    def _extract_key_metrics(self, analysis_results: Dict[str, Any]) -> Dict[str, Any]:
        """Extract key metrics from analysis results"""
        metrics = {}
        
        if "guild_overview" in analysis_results:
            overview = analysis_results["guild_overview"]
            guild_summary = overview.get("guild_summary", {})
            member_stats = overview.get("member_statistics", {})
            
            metrics["guild_size"] = guild_summary.get("member_count", 0)
            metrics["average_level"] = member_stats.get("average_level", 0)
            metrics["average_item_level"] = member_stats.get("average_item_level", 0)
        
        return metrics
    
    def _get_error_suggestions(self, error_type: str) -> List[str]:
        """Get suggestions based on error type"""
        suggestions = {
            "classification_error": [
                "Try a different analysis type",
                "Check if the request format is correct"
            ],
            "analysis_error": [
                "Verify guild and realm names are correct",
                "Check if the guild exists and is accessible"
            ],
            "formatting_error": [
                "Internal error occurred during formatting",
                "Please try again later"
            ]
        }
        
        return suggestions.get(error_type, ["Please try again or contact support"])
    
    def _summarize_character(self, member_data: Dict[str, Any]) -> Dict[str, Any]:
        """Summarize character information"""
        return {
            "name": get_localized_name(member_data),
            "level": member_data.get("level", 0),
            "class": parse_class_info(member_data.get("character_class")),
            "race": get_localized_name(member_data, "race"),
            "guild_rank": member_data.get("guild_rank", 999),
            "achievement_points": member_data.get("achievement_points", 0)
        }
    
    def _analyze_character_performance(self, member_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze character performance"""
        eq_summary = member_data.get("equipment_summary", {})
        
        return {
            "item_level": eq_summary.get("average_item_level", 0),
            "equipment_quality": "High" if eq_summary.get("average_item_level", 0) > 450 else "Standard",
            "gear_score": eq_summary.get("average_item_level", 0) * eq_summary.get("total_items", 0)
        }
    
    def _analyze_equipment(self, member_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze equipment"""
        eq_summary = member_data.get("equipment_summary", {})
        
        return {
            "average_item_level": eq_summary.get("average_item_level", 0),
            "total_equipped": eq_summary.get("total_items", 0),
            "gear_status": "Well-equipped" if eq_summary.get("average_item_level", 0) > 440 else "Needs upgrades"
        }
    
    def _analyze_progression(self, member_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze character progression"""
        level = member_data.get("level", 0)
        
        return {
            "level_status": "Max level" if level >= 80 else f"Level {level}",
            "progression_stage": "Endgame" if level >= 80 else "Leveling"
        }