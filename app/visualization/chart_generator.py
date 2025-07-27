"""
Chart and Visualization Generator
"""

import io
import base64
import logging
from typing import Dict, Any, List, Optional
import plotly.graph_objects as go
import plotly.express as px
import plotly.io as pio
from plotly.subplots import make_subplots
import pandas as pd
from PIL import Image
import numpy as np

from ..utils.wow_utils import get_localized_name, parse_class_info

logger = logging.getLogger(__name__)


class ChartGenerator:
    """Generate charts and visualizations for WoW guild analysis"""
    
    def __init__(self):
        # Set default theme
        pio.templates.default = "plotly_dark"
        
        # WoW class colors for consistency
        self.class_colors = {
            "Death Knight": "#C41E3A",
            "Demon Hunter": "#A330C9",
            "Druid": "#FF7C0A",
            "Evoker": "#33937F",
            "Hunter": "#AAD372",
            "Mage": "#3FC7EB",
            "Monk": "#00FF98",
            "Paladin": "#F48CBA",
            "Priest": "#FFFFFF",
            "Rogue": "#FFF468",
            "Shaman": "#0070DD",
            "Warlock": "#8788EE",
            "Warrior": "#C69B6D"
        }
        
        # Difficulty colors
        self.difficulty_colors = {
            "LFR": "#71D5FF",
            "Normal": "#1EFF00",
            "Heroic": "#0070DD",
            "Mythic": "#FF8000"
        }
    
    async def create_raid_progress_chart(self, guild_data: Dict[str, Any], raid_tier: str = "current") -> str:
        """
        Create raid progression chart
        
        Args:
            guild_data: Guild data from Blizzard API
            raid_tier: Raid tier to analyze
        
        Returns:
            Base64 encoded PNG image
        """
        try:
            # Extract guild achievements for raid progress
            achievements = guild_data.get("guild_achievements", {})
            guild_info = guild_data.get("guild_info", {})
            
            # Mock raid progress data (would be extracted from achievements in real implementation)
            raid_data = self._extract_raid_progress(achievements, raid_tier)
            
            if not raid_data:
                return await self._create_no_data_chart("No raid progression data available")
            
            # Create subplot with multiple difficulty levels
            fig = make_subplots(
                rows=len(raid_data),
                cols=1,
                subplot_titles=[f"{raid['name']} - {raid['tier']}" for raid in raid_data],
                vertical_spacing=0.1
            )
            
            for i, raid in enumerate(raid_data, 1):
                difficulties = raid.get("difficulties", [])
                
                if difficulties:
                    x_labels = [d["difficulty"] for d in difficulties]
                    y_values = [d["bosses_killed"] for d in difficulties]
                    max_bosses = [d["total_bosses"] for d in difficulties]
                    colors = [self.difficulty_colors.get(d, "#CCCCCC") for d in x_labels]
                    
                    # Add progress bars
                    fig.add_trace(
                        go.Bar(
                            x=x_labels,
                            y=y_values,
                            name=f"{raid['name']} Progress",
                            marker_color=colors,
                            text=[f"{killed}/{total}" for killed, total in zip(y_values, max_bosses)],
                            textposition="auto",
                            showlegend=(i == 1)
                        ),
                        row=i, col=1
                    )
                    
                    # Add maximum boss lines
                    for j, (label, max_boss) in enumerate(zip(x_labels, max_bosses)):
                        fig.add_hline(
                            y=max_boss,
                            line_dash="dash",
                            line_color="red",
                            opacity=0.5,
                            row=i, col=1
                        )
            
            # Update layout
            fig.update_layout(
                title={
                    "text": f"Raid Progression - {get_localized_name(guild_info)}",
                    "x": 0.5,
                    "font": {"size": 20, "color": "white"}
                },
                template="plotly_dark",
                height=300 * len(raid_data),
                width=1000,
                showlegend=True,
                font={"color": "white"}
            )
            
            # Convert to image
            img_bytes = pio.to_image(fig, format="png", width=1000, height=300 * len(raid_data))
            img_base64 = base64.b64encode(img_bytes).decode()
            
            logger.info(f"Generated raid progress chart for {len(raid_data)} raids")
            return img_base64
            
        except Exception as e:
            logger.error(f"Error creating raid progress chart: {str(e)}")
            return await self._create_error_chart(f"Error generating chart: {str(e)}")
    
    async def create_member_comparison_chart(self, member_data: List[Dict[str, Any]], metric: str) -> str:
        """
        Create member comparison chart
        
        Args:
            member_data: List of member data
            metric: Metric to compare
        
        Returns:
            Base64 encoded PNG image
        """
        try:
            if not member_data:
                return await self._create_no_data_chart("No member data available for comparison")
            
            # Extract data for comparison
            names = []
            values = []
            classes = []
            colors = []
            
            for member in member_data:
                name = get_localized_name(member)
                names.append(name)
                
                # Extract metric value
                if metric == "item_level":
                    value = member.get("equipment_summary", {}).get("average_item_level", 0)
                elif metric == "achievement_points":
                    value = member.get("achievement_points", 0)
                elif metric == "level":
                    value = member.get("level", 0)
                elif metric == "guild_rank":
                    value = member.get("guild_rank", 999)
                else:
                    value = 0
                
                values.append(value)
                
                # Get class for coloring
                class_name = parse_class_info(member.get("character_class"))
                classes.append(class_name)
                colors.append(self.class_colors.get(class_name, "#CCCCCC"))
            
            # Create bar chart
            fig = go.Figure()
            
            fig.add_trace(go.Bar(
                x=names,
                y=values,
                marker_color=colors,
                text=[f"{v:.1f}" if isinstance(v, float) else str(v) for v in values],
                textposition="auto",
                hovertemplate="<b>%{x}</b><br>" +
                             f"{metric.replace('_', ' ').title()}: %{{y}}<br>" +
                             "Class: %{customdata}<extra></extra>",
                customdata=classes
            ))
            
            # Update layout
            fig.update_layout(
                title={
                    "text": f"Member Comparison - {metric.replace('_', ' ').title()}",
                    "x": 0.5,
                    "font": {"size": 20, "color": "white"}
                },
                xaxis_title="Member Name",
                yaxis_title=metric.replace('_', ' ').title(),
                template="plotly_dark",
                width=max(800, len(names) * 80),
                height=600,
                font={"color": "white"},
                xaxis={"tickangle": -45}
            )
            
            # Convert to image
            img_bytes = pio.to_image(fig, format="png", width=max(800, len(names) * 80), height=600)
            img_base64 = base64.b64encode(img_bytes).decode()
            
            logger.info(f"Generated member comparison chart for {len(member_data)} members")
            return img_base64
            
        except Exception as e:
            logger.error(f"Error creating member comparison chart: {str(e)}")
            return await self._create_error_chart(f"Error generating chart: {str(e)}")
    
    async def create_class_distribution_chart(self, member_data: List[Dict[str, Any]]) -> str:
        """
        Create class distribution pie chart
        
        Args:
            member_data: List of member data
        
        Returns:
            Base64 encoded PNG image
        """
        try:
            if not member_data:
                return await self._create_no_data_chart("No member data available")
            
            # Count classes
            class_counts = {}
            for member in member_data:
                class_name = parse_class_info(member.get("character_class"))
                class_counts[class_name] = class_counts.get(class_name, 0) + 1
            
            # Create pie chart
            fig = go.Figure()
            
            fig.add_trace(go.Pie(
                labels=list(class_counts.keys()),
                values=list(class_counts.values()),
                marker_colors=[self.class_colors.get(cls, "#CCCCCC") for cls in class_counts.keys()],
                textinfo="label+percent+value",
                textposition="auto",
                hovertemplate="<b>%{label}</b><br>" +
                             "Count: %{value}<br>" +
                             "Percentage: %{percent}<extra></extra>"
            ))
            
            # Update layout
            fig.update_layout(
                title={
                    "text": "Guild Class Distribution",
                    "x": 0.5,
                    "font": {"size": 20, "color": "white"}
                },
                template="plotly_dark",
                width=800,
                height=600,
                font={"color": "white"}
            )
            
            # Convert to image
            img_bytes = pio.to_image(fig, format="png", width=800, height=600)
            img_base64 = base64.b64encode(img_bytes).decode()
            
            logger.info(f"Generated class distribution chart for {len(class_counts)} classes")
            return img_base64
            
        except Exception as e:
            logger.error(f"Error creating class distribution chart: {str(e)}")
            return await self._create_error_chart(f"Error generating chart: {str(e)}")
    
    async def create_level_distribution_chart(self, member_data: List[Dict[str, Any]]) -> str:
        """
        Create level distribution histogram
        
        Args:
            member_data: List of member data
        
        Returns:
            Base64 encoded PNG image
        """
        try:
            if not member_data:
                return await self._create_no_data_chart("No member data available")
            
            # Extract levels
            levels = [member.get("level", 0) for member in member_data]
            
            # Create histogram
            fig = go.Figure()
            
            fig.add_trace(go.Histogram(
                x=levels,
                nbinsx=20,
                marker_color="#3FC7EB",
                opacity=0.7,
                hovertemplate="Level Range: %{x}<br>" +
                             "Member Count: %{y}<extra></extra>"
            ))
            
            # Update layout
            fig.update_layout(
                title={
                    "text": "Guild Level Distribution",
                    "x": 0.5,
                    "font": {"size": 20, "color": "white"}
                },
                xaxis_title="Character Level",
                yaxis_title="Number of Members",
                template="plotly_dark",
                width=800,
                height=600,
                font={"color": "white"}
            )
            
            # Convert to image
            img_bytes = pio.to_image(fig, format="png", width=800, height=600)
            img_base64 = base64.b64encode(img_bytes).decode()
            
            logger.info(f"Generated level distribution chart for {len(member_data)} members")
            return img_base64
            
        except Exception as e:
            logger.error(f"Error creating level distribution chart: {str(e)}")
            return await self._create_error_chart(f"Error generating chart: {str(e)}")
    
    def _extract_raid_progress(self, achievements: Dict[str, Any], raid_tier: str) -> List[Dict[str, Any]]:
        """Extract raid progress from achievement data"""
        # Mock implementation - would parse actual achievement data
        return [
            {
                "name": "Amirdrassil, the Dream's Hope",
                "tier": "Dragonflight",
                "difficulties": [
                    {"difficulty": "LFR", "bosses_killed": 9, "total_bosses": 9},
                    {"difficulty": "Normal", "bosses_killed": 7, "total_bosses": 9},
                    {"difficulty": "Heroic", "bosses_killed": 4, "total_bosses": 9},
                    {"difficulty": "Mythic", "bosses_killed": 1, "total_bosses": 9},
                ]
            }
        ]
    
    async def _create_no_data_chart(self, message: str) -> str:
        """Create a chart indicating no data available"""
        fig = go.Figure()
        
        fig.add_annotation(
            text=message,
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            xanchor="center", yanchor="middle",
            font={"size": 24, "color": "white"}
        )
        
        fig.update_layout(
            template="plotly_dark",
            width=800,
            height=400,
            showlegend=False,
            xaxis={"visible": False},
            yaxis={"visible": False}
        )
        
        img_bytes = pio.to_image(fig, format="png", width=800, height=400)
        return base64.b64encode(img_bytes).decode()
    
    async def _create_error_chart(self, error_message: str) -> str:
        """Create a chart indicating an error occurred"""
        fig = go.Figure()
        
        fig.add_annotation(
            text=f"⚠️ {error_message}",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            xanchor="center", yanchor="middle",
            font={"size": 20, "color": "red"}
        )
        
        fig.update_layout(
            template="plotly_dark",
            width=800,
            height=400,
            showlegend=False,
            xaxis={"visible": False},
            yaxis={"visible": False}
        )
        
        img_bytes = pio.to_image(fig, format="png", width=800, height=400)
        return base64.b64encode(img_bytes).decode()