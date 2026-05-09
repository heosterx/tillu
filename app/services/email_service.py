"""
Email Intelligence Service
Gmail API integration for email analysis and smart responses
"""
import httpx
import base64
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from app.config import settings
from app.utils.database import db
from app.utils.logging import get_logger
from app.utils.google_auth import get_access_token
from app.transformers.classifiers import emotion_detector, stress_detector
from app.transformers.extractors import ner_extractor, summarizer

logger = get_logger("email_service")


class EmailService:
    """
    Email intelligence and analysis service
    Integrates with Gmail API for fetching and analyzing emails
    """
    
    GMAIL_API = "https://gmail.googleapis.com/gmail/v1"
    
    def __init__(self):
        self.gmail_enabled = bool(settings.google_client_id and settings.gmail_refresh_token)
    
    async def fetch_and_analyze(
        self,
        user_id: str,
        max_emails: int = 10,
        since_hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Fetch emails and analyze for importance/urgency
        
        Args:
            user_id: User to fetch emails for
            max_emails: Maximum emails to process
            since_hours: Only fetch emails from last N hours
            
        Returns:
            List of analyzed emails
        """
        if not self.gmail_enabled:
            logger.warning("Gmail API not configured")
            return []
        
        analyzed = []
        
        try:
            # Fetch emails from Gmail API
            emails = await self._fetch_gmail_emails(user_id, max_emails, since_hours)
            
            for email in emails:
                # Analyze email
                analysis = await self._analyze_email(email)
                
                # Store email intelligence
                email_record = {
                    "user_id": user_id,
                    "email_id": email.get("id"),
                    "thread_id": email.get("threadId"),
                    "sender": analysis.get("sender"),
                    "subject": analysis.get("subject"),
                    "summary": analysis.get("summary"),
                    "importance_score": analysis.get("importance", 5),
                    "sentiment": analysis.get("sentiment"),
                    "entities": analysis.get("entities"),
                    "requires_response": analysis.get("requires_response", False),
                    "suggested_response": analysis.get("suggested_response"),
                    "received_at": analysis.get("date"),
                    "analyzed_at": datetime.now().isoformat()
                }
                
                # Check if already exists
                existing = await db.fetch_one(
                    "emails",
                    {"email_id": email.get("id")}
                )
                
                if not existing:
                    result = await db.insert("emails", email_record)
                    if result:
                        analyzed.append(email_record)
                
        except Exception as e:
            logger.error(f"Email fetch and analyze error: {e}")
        
        logger.info(f"Analyzed {len(analyzed)} new emails")
        return analyzed
    
    async def _fetch_gmail_emails(
        self,
        user_id: str,
        max_results: int = 10,
        since_hours: int = 24
    ) -> List[Dict]:
        """Fetch emails from Gmail API"""
        emails = []
        
        try:
            # Calculate time threshold
            since = (datetime.now() - timedelta(hours=since_hours)).strftime("%Y/%m/%d")
            query = f"after:{since}"

            token = await get_access_token()
            if not token:
                logger.error("Could not obtain Google access token")
                return []

            # List messages
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.GMAIL_API}/users/me/messages",
                    params={"q": query, "maxResults": max_results},
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=15.0
                )

                if response.status_code == 200:
                    data = response.json()
                    messages = data.get("messages", [])

                    for msg in messages:
                        # Fetch full message
                        msg_response = await client.get(
                            f"{self.GMAIL_API}/users/me/messages/{msg['id']}",
                            headers={"Authorization": f"Bearer {token}"},
                            timeout=10.0
                        )

                        if msg_response.status_code == 200:
                            emails.append(msg_response.json())
                            
        except Exception as e:
            logger.error(f"Gmail API error: {e}")
        
        return emails
    
    async def _analyze_email(self, email: Dict) -> Dict[str, Any]:
        """Analyze email content for importance and sentiment"""
        # Extract headers
        headers = {h["name"]: h["value"] for h in email.get("payload", {}).get("headers", [])}
        
        subject = headers.get("Subject", "No Subject")
        sender = headers.get("From", "Unknown")
        date = headers.get("Date", datetime.now().isoformat())
        
        # Extract body
        body = self._extract_body(email.get("payload", {}))
        
        # Analyze content
        full_text = f"{subject}\n{body}"
        
        # Run transformers
        emotion_result = await emotion_detector.detect(full_text)
        stress_result = await stress_detector.detect(full_text)
        
        # Summarize if long
        summary = body[:200]
        if len(body) > 300:
            try:
                summary = await summarizer.summarize(body, max_length=150)
            except:
                summary = body[:200]
        
        # Extract entities
        entities = []
        try:
            entities = await ner_extractor.extract(full_text)
        except:
            pass
        
        # Calculate importance score (1-10)
        importance = 5
        
        # Boost for urgency keywords
        urgency_keywords = ["urgent", "asap", "deadline", "important", "action required"]
        if any(kw in full_text.lower() for kw in urgency_keywords):
            importance += 2
        
        # Boost for high stress/sentiment
        if stress_result.get("stress_level") == "high":
            importance += 1
        
        # Boost if from known important contact
        # In production: check against people_knowledge
        
        # Determine if response required
        requires_response = any(
            kw in full_text.lower()
            for kw in ["please reply", "let me know", "your thoughts", "feedback"]
        )
        
        # Generate suggested response
        suggested_response = None
        if requires_response:
            suggested_response = self._generate_response_suggestion(subject, body, emotion_result)
        
        return {
            "sender": sender,
            "subject": subject,
            "date": date,
            "body_preview": body[:500],
            "summary": summary,
            "importance": min(10, importance),
            "sentiment": emotion_result.get("dominant_emotion", "neutral"),
            "stress_level": stress_result.get("stress_level", "low"),
            "entities": entities,
            "requires_response": requires_response,
            "suggested_response": suggested_response
        }
    
    def _extract_body(self, payload: Dict) -> str:
        """Extract email body from payload"""
        body = ""
        
        if "parts" in payload:
            for part in payload["parts"]:
                if part.get("mimeType") == "text/plain":
                    data = part.get("body", {}).get("data", "")
                    if data:
                        body += base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                elif part.get("mimeType") == "text/html":
                    # Skip HTML for now, prefer plain text
                    pass
        else:
            data = payload.get("body", {}).get("data", "")
            if data:
                body = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
        
        return body[:5000]  # Limit size
    
    def _generate_response_suggestion(
        self,
        subject: str,
        body: str,
        emotion: Dict
    ) -> Optional[str]:
        """Generate suggested response based on email content"""
        # Simple template-based suggestions
        # In production: use LLM for smart suggestions
        
        emotion_type = emotion.get("dominant_emotion", "neutral")
        
        if emotion_type in ["anger", "frustration"]:
            return "Acknowledge their concern and offer to help resolve the issue."
        elif emotion_type in ["joy", "excitement"]:
            return "Match their enthusiasm and express appreciation."
        elif "question" in body.lower():
            return "Answer their specific question directly and concisely."
        else:
            return "Thank them for their message and respond to the key points."
    
    async def get_priority_inbox(self, user_id: str, min_importance: int = 7) -> List[Dict]:
        """Get high-priority emails requiring attention"""
        emails = await db.fetch_many(
            "emails",
            filters={
                "user_id": user_id,
                "importance_score": (">=", min_importance
            )},
            order_by="received_at",
            ascending=False,
            limit=20
        )
        
        return [
            {
                "id": e.get("id"),
                "sender": e.get("sender"),
                "subject": e.get("subject"),
                "summary": e.get("summary"),
                "importance": e.get("importance_score"),
                "requires_response": e.get("requires_response"),
                "suggested_response": e.get("suggested_response"),
                "received_at": e.get("received_at")
            }
            for e in emails
        ]


# Singleton
email_service = EmailService()
