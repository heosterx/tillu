"""
YouTube Tools Integration using CrewAI

Provides semantic search within YouTube video content using RAG (Retrieval-Augmented Generation).
Enables agents to search across YouTube or target specific video URLs.

Features:
- Semantic search within video transcripts
- Multi-language support (Hindi/English)
- Video metadata extraction
- Transcript-based RAG search
- Batch video processing
"""

import httpx
from typing import Any, Dict, List, Optional
from datetime import datetime
import asyncio

from app.config import settings
from app.tools.registry import BaseTool, ToolMetadata, ToolRegistry
from app.utils.logging import get_logger

logger = get_logger("youtube_tools")

# Try to import CrewAI YouTube tools
try:
    from crewai_tools import YoutubeVideoSearchTool
    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False
    logger.warning("CrewAI not available, YouTube tools will use fallback implementation")


class YouTubeSearchTool(BaseTool):
    """
    Semantic search within YouTube video content using RAG.
    
    Searches across YouTube or targets specific video URLs.
    Returns video metadata, transcript excerpts, and relevance scores.
    """
    
    metadata = ToolMetadata(
        name="tool_youtube_search",
        description="Search YouTube videos semantically using RAG. Can search across YouTube or specific video URLs. Returns video metadata, transcript excerpts, and timestamps.",
        parameters={
            "query": {"type": "string", "description": "Search query for YouTube videos"},
            "video_url": {"type": "string", "description": "Optional: Specific YouTube video URL to search within", "default": None},
            "max_results": {"type": "integer", "description": "Maximum number of results (1-20)", "default": 5},
            "lang": {"type": "string", "description": "Language: hi | en | auto", "default": "auto"},
            "include_transcript": {"type": "boolean", "description": "Include full transcript in results", "default": False},
        },
        rate_limited=True
    )
    
    def __init__(self):
        super().__init__()
        self.crewai_tool = None
        if CREWAI_AVAILABLE:
            try:
                self.crewai_tool = YoutubeVideoSearchTool()
                logger.info("CrewAI YouTube tool initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize CrewAI YouTube tool: {e}")
    
    async def execute(
        self,
        query: str,
        video_url: Optional[str] = None,
        max_results: int = 5,
        lang: str = "auto",
        include_transcript: bool = False
    ) -> Dict[str, Any]:
        """
        Execute YouTube semantic search.
        
        Args:
            query: Search query
            video_url: Optional specific video URL to search within
            max_results: Maximum results to return
            lang: Language (hi/en/auto)
            include_transcript: Whether to include full transcript
            
        Returns:
            Search results with video metadata and transcript excerpts
        """
        try:
            # Use CrewAI tool if available
            if self.crewai_tool:
                return await self._search_with_crewai(
                    query, video_url, max_results, lang, include_transcript
                )
            else:
                return await self._search_fallback(
                    query, video_url, max_results, lang, include_transcript
                )
        except Exception as e:
            logger.error(f"YouTube search error: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": query
            }
    
    async def _search_with_crewai(
        self,
        query: str,
        video_url: Optional[str],
        max_results: int,
        lang: str,
        include_transcript: bool
    ) -> Dict[str, Any]:
        """Search using CrewAI YouTube tool"""
        try:
            # Prepare search query with language context
            lang_context = "in Hindi" if lang == "hi" else "in English" if lang == "en" else ""
            search_query = f"{query} {lang_context}".strip()
            
            # If specific video URL provided, search within that video
            if video_url:
                search_query = f"Search in {video_url}: {search_query}"
            
            # Execute CrewAI tool (runs synchronously, wrap in executor)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.crewai_tool.run(search_query)
            )
            
            # Parse CrewAI result
            videos = self._parse_crewai_result(result, max_results)
            
            return {
                "success": True,
                "query": query,
                "video_url": video_url,
                "lang": lang,
                "results": videos,
                "result_count": len(videos),
                "source": "crewai_youtube",
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"CrewAI YouTube search failed: {e}")
            raise
    
    async def _search_fallback(
        self,
        query: str,
        video_url: Optional[str],
        max_results: int,
        lang: str,
        include_transcript: bool
    ) -> Dict[str, Any]:
        """Fallback YouTube search using YouTube Data API"""
        try:
            if not settings.youtube_api_key:
                return {
                    "success": False,
                    "error": "YouTube API key not configured",
                    "query": query
                }
            
            # If specific video URL provided, extract video ID and get transcript
            if video_url:
                video_id = self._extract_video_id(video_url)
                if video_id:
                    return await self._search_video_transcript(
                        video_id, query, lang, include_transcript
                    )
            
            # Search YouTube for videos
            videos = await self._search_youtube_api(query, max_results, lang)
            
            return {
                "success": True,
                "query": query,
                "video_url": video_url,
                "lang": lang,
                "results": videos,
                "result_count": len(videos),
                "source": "youtube_api",
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"YouTube fallback search failed: {e}")
            raise
    
    async def _search_youtube_api(
        self,
        query: str,
        max_results: int,
        lang: str
    ) -> List[Dict[str, Any]]:
        """Search YouTube using YouTube Data API"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Search for videos
                search_params = {
                    "part": "snippet",
                    "q": query,
                    "type": "video",
                    "maxResults": min(max_results, 20),
                    "key": settings.youtube_api_key,
                    "relevanceLanguage": "hi" if lang == "hi" else "en",
                    "order": "relevance"
                }
                
                resp = await client.get(
                    "https://www.googleapis.com/youtube/v3/search",
                    params=search_params
                )
                
                if resp.status_code != 200:
                    logger.error(f"YouTube API error: {resp.status_code}")
                    return []
                
                data = resp.json()
                videos = []
                
                for item in data.get("items", [])[:max_results]:
                    video_id = item.get("id", {}).get("videoId")
                    if not video_id:
                        continue
                    
                    snippet = item.get("snippet", {})
                    videos.append({
                        "video_id": video_id,
                        "url": f"https://www.youtube.com/watch?v={video_id}",
                        "title": snippet.get("title", ""),
                        "description": snippet.get("description", "")[:500],
                        "channel": snippet.get("channelTitle", ""),
                        "published_at": snippet.get("publishedAt", ""),
                        "thumbnail": snippet.get("thumbnails", {}).get("medium", {}).get("url", ""),
                        "relevance_score": 0.9  # YouTube API doesn't provide explicit scores
                    })
                
                return videos
                
        except Exception as e:
            logger.error(f"YouTube API search error: {e}")
            return []
    
    async def _search_video_transcript(
        self,
        video_id: str,
        query: str,
        lang: str,
        include_transcript: bool
    ) -> Dict[str, Any]:
        """Search within a specific video's transcript"""
        try:
            # Get video metadata
            video_info = await self._get_video_info(video_id)
            
            # Get transcript
            transcript = await self._get_transcript(video_id, lang)
            
            if not transcript:
                return {
                    "success": False,
                    "error": f"Could not retrieve transcript for video {video_id}",
                    "video_id": video_id
                }
            
            # Search within transcript
            matches = self._search_transcript(transcript, query, lang)
            
            result = {
                "success": True,
                "query": query,
                "video_id": video_id,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "title": video_info.get("title", ""),
                "channel": video_info.get("channel", ""),
                "matches": matches,
                "match_count": len(matches),
                "source": "video_transcript",
                "timestamp": datetime.now().isoformat()
            }
            
            if include_transcript:
                result["full_transcript"] = transcript
            
            return result
            
        except Exception as e:
            logger.error(f"Video transcript search error: {e}")
            raise
    
    async def _get_video_info(self, video_id: str) -> Dict[str, Any]:
        """Get video metadata from YouTube API"""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                params = {
                    "part": "snippet,contentDetails,statistics",
                    "id": video_id,
                    "key": settings.youtube_api_key
                }
                
                resp = await client.get(
                    "https://www.googleapis.com/youtube/v3/videos",
                    params=params
                )
                
                if resp.status_code == 200:
                    items = resp.json().get("items", [])
                    if items:
                        snippet = items[0].get("snippet", {})
                        stats = items[0].get("statistics", {})
                        return {
                            "title": snippet.get("title", ""),
                            "channel": snippet.get("channelTitle", ""),
                            "description": snippet.get("description", ""),
                            "published_at": snippet.get("publishedAt", ""),
                            "view_count": stats.get("viewCount", 0),
                            "like_count": stats.get("likeCount", 0),
                            "comment_count": stats.get("commentCount", 0),
                        }
                
                return {}
                
        except Exception as e:
            logger.error(f"Get video info error: {e}")
            return {}
    
    async def _get_transcript(self, video_id: str, lang: str) -> Optional[str]:
        """Get video transcript using youtube-transcript-api"""
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            
            # Try to get transcript in requested language
            try:
                transcript_list = YouTubeTranscriptApi.get_transcript(
                    video_id,
                    languages=["hi"] if lang == "hi" else ["en"]
                )
            except:
                # Fallback to any available language
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
            
            # Combine transcript entries
            transcript = " ".join([entry["text"] for entry in transcript_list])
            return transcript
            
        except ImportError:
            logger.warning("youtube-transcript-api not installed, cannot retrieve transcripts")
            return None
        except Exception as e:
            logger.error(f"Get transcript error: {e}")
            return None
    
    def _search_transcript(
        self,
        transcript: str,
        query: str,
        lang: str
    ) -> List[Dict[str, Any]]:
        """Search within transcript text"""
        import re
        
        matches = []
        query_lower = query.lower()
        
        # Split transcript into sentences
        sentences = re.split(r'[.!?]+', transcript)
        
        for i, sentence in enumerate(sentences):
            sentence_lower = sentence.lower()
            
            # Check if query matches
            if query_lower in sentence_lower:
                # Calculate relevance score based on query position and frequency
                relevance = 1.0
                
                # Boost score if query is at the beginning
                if sentence_lower.startswith(query_lower):
                    relevance += 0.2
                
                # Count query occurrences
                occurrences = sentence_lower.count(query_lower)
                relevance += (occurrences - 1) * 0.1
                
                matches.append({
                    "text": sentence.strip(),
                    "position": i,
                    "relevance_score": min(relevance, 1.0),
                    "timestamp": self._estimate_timestamp(i, len(sentences))
                })
        
        # Sort by relevance
        matches.sort(key=lambda x: x["relevance_score"], reverse=True)
        
        return matches[:10]  # Return top 10 matches
    
    def _extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from YouTube URL"""
        import re
        
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&\n?#]+)',
            r'youtube\.com\/embed\/([^&\n?#]+)',
            r'youtube\.com\/v\/([^&\n?#]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    def _estimate_timestamp(self, position: int, total: int) -> str:
        """Estimate timestamp in video based on position in transcript"""
        # Rough estimate: assume average speaking rate
        # This is a fallback; actual timestamps should come from transcript API
        seconds = int((position / total) * 3600)  # Assume 1 hour video
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes:02d}:{secs:02d}"
    
    def _parse_crewai_result(self, result: str, max_results: int) -> List[Dict[str, Any]]:
        """Parse CrewAI tool result into structured format"""
        # CrewAI returns results as formatted text
        # Parse and structure the results
        videos = []
        
        # Simple parsing - in production, use more robust parsing
        lines = result.split('\n')
        current_video = {}
        
        for line in lines:
            line = line.strip()
            if not line:
                if current_video:
                    videos.append(current_video)
                    current_video = {}
                continue
            
            if 'title' in line.lower():
                current_video['title'] = line.split(':', 1)[-1].strip()
            elif 'url' in line.lower() or 'youtube.com' in line:
                current_video['url'] = line.split(':', 1)[-1].strip() if ':' in line else line
            elif 'channel' in line.lower():
                current_video['channel'] = line.split(':', 1)[-1].strip()
            elif 'description' in line.lower():
                current_video['description'] = line.split(':', 1)[-1].strip()
        
        if current_video:
            videos.append(current_video)
        
        return videos[:max_results]


class YouTubeTranscriptTool(BaseTool):
    """
    Extract and analyze YouTube video transcripts.
    
    Retrieves full transcripts with timestamps and supports
    multi-language transcripts.
    """
    
    metadata = ToolMetadata(
        name="tool_youtube_transcript",
        description="Extract YouTube video transcript with timestamps. Supports multiple languages and returns structured transcript data.",
        parameters={
            "video_url": {"type": "string", "description": "YouTube video URL"},
            "lang": {"type": "string", "description": "Language: hi | en | auto", "default": "auto"},
            "include_timestamps": {"type": "boolean", "description": "Include timestamps for each entry", "default": True},
        },
        rate_limited=True
    )
    
    async def execute(
        self,
        video_url: str,
        lang: str = "auto",
        include_timestamps: bool = True
    ) -> Dict[str, Any]:
        """
        Extract YouTube transcript.
        
        Args:
            video_url: YouTube video URL
            lang: Language preference
            include_timestamps: Whether to include timestamps
            
        Returns:
            Transcript data with metadata
        """
        try:
            # Extract video ID
            video_id = YouTubeSearchTool()._extract_video_id(video_url)
            if not video_id:
                return {
                    "success": False,
                    "error": "Invalid YouTube URL",
                    "url": video_url
                }
            
            # Get video info
            search_tool = YouTubeSearchTool()
            video_info = await search_tool._get_video_info(video_id)
            
            # Get transcript
            transcript_text = await search_tool._get_transcript(video_id, lang)
            
            if not transcript_text:
                return {
                    "success": False,
                    "error": "Could not retrieve transcript",
                    "video_id": video_id
                }
            
            # Parse transcript with timestamps if available
            transcript_entries = await self._parse_transcript_with_timestamps(
                video_id, lang, include_timestamps
            )
            
            return {
                "success": True,
                "video_id": video_id,
                "url": video_url,
                "title": video_info.get("title", ""),
                "channel": video_info.get("channel", ""),
                "transcript": transcript_text,
                "entries": transcript_entries,
                "entry_count": len(transcript_entries),
                "language": lang,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Transcript extraction error: {e}")
            return {
                "success": False,
                "error": str(e),
                "url": video_url
            }
    
    async def _parse_transcript_with_timestamps(
        self,
        video_id: str,
        lang: str,
        include_timestamps: bool
    ) -> List[Dict[str, Any]]:
        """Parse transcript with timestamps"""
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            
            try:
                transcript_list = YouTubeTranscriptApi.get_transcript(
                    video_id,
                    languages=["hi"] if lang == "hi" else ["en"]
                )
            except:
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
            
            entries = []
            for entry in transcript_list:
                entries.append({
                    "text": entry.get("text", ""),
                    "timestamp": entry.get("start", 0) if include_timestamps else None,
                    "duration": entry.get("duration", 0) if include_timestamps else None,
                })
            
            return entries
            
        except ImportError:
            logger.warning("youtube-transcript-api not installed")
            return []
        except Exception as e:
            logger.error(f"Parse transcript error: {e}")
            return []


class YouTubeChannelAnalysisTool(BaseTool):
    """
    Analyze YouTube channel content and trends.
    
    Retrieves channel statistics, recent videos, and content analysis.
    """
    
    metadata = ToolMetadata(
        name="tool_youtube_channel_analysis",
        description="Analyze YouTube channel: statistics, recent videos, content trends, and engagement metrics.",
        parameters={
            "channel_url": {"type": "string", "description": "YouTube channel URL or channel ID"},
            "max_videos": {"type": "integer", "description": "Maximum recent videos to analyze", "default": 10},
            "lang": {"type": "string", "description": "Language: hi | en | auto", "default": "auto"},
        },
        rate_limited=True
    )
    
    async def execute(
        self,
        channel_url: str,
        max_videos: int = 10,
        lang: str = "auto"
    ) -> Dict[str, Any]:
        """
        Analyze YouTube channel.
        
        Args:
            channel_url: Channel URL or ID
            max_videos: Maximum recent videos to analyze
            lang: Language preference
            
        Returns:
            Channel analysis with statistics and trends
        """
        try:
            if not settings.youtube_api_key:
                return {
                    "success": False,
                    "error": "YouTube API key not configured",
                    "channel_url": channel_url
                }
            
            # Extract channel ID
            channel_id = self._extract_channel_id(channel_url)
            if not channel_id:
                return {
                    "success": False,
                    "error": "Invalid channel URL",
                    "channel_url": channel_url
                }
            
            # Get channel info
            channel_info = await self._get_channel_info(channel_id)
            
            # Get recent videos
            recent_videos = await self._get_recent_videos(channel_id, max_videos)
            
            # Analyze content
            analysis = self._analyze_content(recent_videos)
            
            return {
                "success": True,
                "channel_id": channel_id,
                "channel_url": channel_url,
                "channel_info": channel_info,
                "recent_videos": recent_videos,
                "analysis": analysis,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Channel analysis error: {e}")
            return {
                "success": False,
                "error": str(e),
                "channel_url": channel_url
            }
    
    async def _get_channel_info(self, channel_id: str) -> Dict[str, Any]:
        """Get channel information"""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                params = {
                    "part": "snippet,statistics,contentDetails",
                    "id": channel_id,
                    "key": settings.youtube_api_key
                }
                
                resp = await client.get(
                    "https://www.googleapis.com/youtube/v3/channels",
                    params=params
                )
                
                if resp.status_code == 200:
                    items = resp.json().get("items", [])
                    if items:
                        item = items[0]
                        snippet = item.get("snippet", {})
                        stats = item.get("statistics", {})
                        return {
                            "title": snippet.get("title", ""),
                            "description": snippet.get("description", "")[:500],
                            "thumbnail": snippet.get("thumbnails", {}).get("medium", {}).get("url", ""),
                            "subscriber_count": stats.get("subscriberCount", 0),
                            "view_count": stats.get("viewCount", 0),
                            "video_count": stats.get("videoCount", 0),
                        }
                
                return {}
                
        except Exception as e:
            logger.error(f"Get channel info error: {e}")
            return {}
    
    async def _get_recent_videos(self, channel_id: str, max_videos: int) -> List[Dict[str, Any]]:
        """Get recent videos from channel"""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                params = {
                    "part": "snippet",
                    "channelId": channel_id,
                    "maxResults": min(max_videos, 50),
                    "order": "date",
                    "key": settings.youtube_api_key
                }
                
                resp = await client.get(
                    "https://www.googleapis.com/youtube/v3/search",
                    params=params
                )
                
                if resp.status_code == 200:
                    videos = []
                    for item in resp.json().get("items", [])[:max_videos]:
                        if item.get("id", {}).get("kind") == "youtube#video":
                            snippet = item.get("snippet", {})
                            videos.append({
                                "video_id": item.get("id", {}).get("videoId"),
                                "title": snippet.get("title", ""),
                                "published_at": snippet.get("publishedAt", ""),
                                "description": snippet.get("description", "")[:200],
                            })
                    return videos
                
                return []
                
        except Exception as e:
            logger.error(f"Get recent videos error: {e}")
            return []
    
    def _extract_channel_id(self, url: str) -> Optional[str]:
        """Extract channel ID from URL"""
        import re
        
        # Direct channel ID
        if url.startswith("UC") and len(url) == 24:
            return url
        
        patterns = [
            r'youtube\.com\/channel\/([^/?]+)',
            r'youtube\.com\/@([^/?]+)',
            r'youtube\.com\/user\/([^/?]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    def _analyze_content(self, videos: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze content trends"""
        if not videos:
            return {}
        
        # Calculate average metrics
        total_videos = len(videos)
        
        # Extract publish dates
        from datetime import datetime as dt
        dates = []
        for video in videos:
            try:
                date = dt.fromisoformat(video.get("published_at", "").replace("Z", "+00:00"))
                dates.append(date)
            except:
                pass
        
        # Calculate upload frequency
        upload_frequency = "Unknown"
        if len(dates) > 1:
            dates.sort()
            time_span = (dates[-1] - dates[0]).days
            if time_span > 0:
                frequency = total_videos / (time_span / 30)  # Videos per month
                if frequency > 10:
                    upload_frequency = "Very Frequent (>10/month)"
                elif frequency > 5:
                    upload_frequency = "Frequent (5-10/month)"
                elif frequency > 2:
                    upload_frequency = "Regular (2-5/month)"
                else:
                    upload_frequency = "Occasional (<2/month)"
        
        return {
            "total_videos_analyzed": total_videos,
            "upload_frequency": upload_frequency,
            "latest_upload": dates[-1].isoformat() if dates else None,
            "oldest_upload": dates[0].isoformat() if dates else None,
        }


# Register tools
ToolRegistry.register(YouTubeSearchTool())
ToolRegistry.register(YouTubeTranscriptTool())
ToolRegistry.register(YouTubeChannelAnalysisTool())

logger.info("YouTube tools registered successfully")
