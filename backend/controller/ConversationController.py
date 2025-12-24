"""
Conversation Controller for MAHIKS-TR
Handles chat conversation and message endpoints
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

from backend.core.security import get_current_user
from backend.database.mysql_handler import MySQLHandler
from backend.core.api_response import success_response, error_response

# Will be injected from main.py
mysql_handler: MySQLHandler = None

def set_mysql_handler(handler: MySQLHandler):
    global mysql_handler
    mysql_handler = handler

conversation_router = APIRouter(prefix="/api/conversations", tags=["conversations"])


# ============================================
# Pydantic Schemas
# ============================================

class CreateConversationRequest(BaseModel):
    title: Optional[str] = Field(default="Yeni Sohbet", max_length=255)


class UpdateConversationRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)


class AddMessageRequest(BaseModel):
    content: str = Field(..., min_length=1)
    sender: str = Field(..., pattern="^(user|agent)$")


class MessageResponse(BaseModel):
    id: int
    conversation_id: int
    content: str
    sender: str
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationResponse(BaseModel):
    id: int
    user_id: int
    title: str
    message_count: int
    last_message: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConversationWithMessagesResponse(BaseModel):
    id: int
    user_id: int
    title: str
    created_at: datetime
    updated_at: datetime
    messages: List[MessageResponse]

    class Config:
        from_attributes = True


# ============================================
# Endpoints
# ============================================

@conversation_router.post("")
async def create_conversation(
    request: CreateConversationRequest,
    current_user: dict = Depends(get_current_user)
):
    """Create a new conversation"""
    try:
        conversation_id = mysql_handler.create_conversation(
            user_id=current_user["id"],
            title=request.title
        )
        
        # Add initial agent message
        mysql_handler.add_message(
            conversation_id=conversation_id,
            content="Merhaba! Ben sağlık sigortası asistanınızım. Size nasıl yardımcı olabilirim?",
            sender="agent"
        )
        
        return success_response(
            data={"conversation_id": conversation_id},
            message="Conversation created successfully",
            status_code=201
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@conversation_router.get("")
async def get_conversations(current_user: dict = Depends(get_current_user)):
    """Get all conversations for the current user"""
    try:
        conversations = mysql_handler.get_conversations_by_user(current_user["id"])
        
        # Format response
        formatted = []
        for conv in conversations:
            formatted.append({
                "id": conv["id"],
                "user_id": conv["user_id"],
                "title": conv["title"],
                "message_count": conv["message_count"] or 0,
                "last_message": conv["last_message"],
                "created_at": conv["created_at"].isoformat() if conv["created_at"] else None,
                "updated_at": conv["updated_at"].isoformat() if conv["updated_at"] else None
            })
        
        return success_response(data=formatted)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@conversation_router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific conversation with its messages"""
    try:
        conversation = mysql_handler.get_conversation_by_id(conversation_id, current_user["id"])
        
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        messages = mysql_handler.get_messages_by_conversation(conversation_id)
        
        # Format messages
        formatted_messages = []
        for msg in messages:
            formatted_messages.append({
                "id": msg["id"],
                "conversation_id": msg["conversation_id"],
                "content": msg["content"],
                "sender": msg["sender"],
                "created_at": msg["created_at"].isoformat() if msg["created_at"] else None
            })
        
        return success_response(data={
            "id": conversation["id"],
            "user_id": conversation["user_id"],
            "title": conversation["title"],
            "created_at": conversation["created_at"].isoformat() if conversation["created_at"] else None,
            "updated_at": conversation["updated_at"].isoformat() if conversation["updated_at"] else None,
            "messages": formatted_messages
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@conversation_router.patch("/{conversation_id}")
async def update_conversation(
    conversation_id: int,
    request: UpdateConversationRequest,
    current_user: dict = Depends(get_current_user)
):
    """Update conversation title"""
    try:
        success = mysql_handler.update_conversation_title(
            conversation_id=conversation_id,
            user_id=current_user["id"],
            title=request.title
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        return success_response(message="Conversation updated successfully")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@conversation_router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Delete a conversation"""
    try:
        success = mysql_handler.delete_conversation(
            conversation_id=conversation_id,
            user_id=current_user["id"]
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        return success_response(message="Conversation deleted successfully")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@conversation_router.post("/{conversation_id}/messages")
async def add_message(
    conversation_id: int,
    request: AddMessageRequest,
    current_user: dict = Depends(get_current_user)
):
    """Add a message to a conversation"""
    try:
        # Verify conversation belongs to user
        conversation = mysql_handler.get_conversation_by_id(conversation_id, current_user["id"])
        
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        message_id = mysql_handler.add_message(
            conversation_id=conversation_id,
            content=request.content,
            sender=request.sender
        )
        
        return success_response(
            data={"message_id": message_id},
            message="Message added successfully",
            status_code=201
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@conversation_router.get("/{conversation_id}/messages")
async def get_messages(
    conversation_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get all messages for a conversation"""
    try:
        # Verify conversation belongs to user
        conversation = mysql_handler.get_conversation_by_id(conversation_id, current_user["id"])
        
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        messages = mysql_handler.get_messages_by_conversation(conversation_id)
        
        # Format messages
        formatted = []
        for msg in messages:
            formatted.append({
                "id": msg["id"],
                "conversation_id": msg["conversation_id"],
                "content": msg["content"],
                "sender": msg["sender"],
                "created_at": msg["created_at"].isoformat() if msg["created_at"] else None
            })
        
        return success_response(data=formatted)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))