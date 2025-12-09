"""Doctor Blog & Experience Sharing Module"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlmodel import Session, select, func, or_, and_
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
import re
import json
import math

from database import get_session
from models import (
    User, UserRole, DoctorProfile,
    BlogPost, BlogComment, BlogLike, CommentLike, BlogFollower, BlogView,
    BlogPostStatus, BlogCategory
)
from dependencies import get_current_user, require_role

router = APIRouter(prefix="/api/blog", tags=["Blog"])


# ==================== SCHEMAS ====================

class BlogPostCreate(BaseModel):
    title: str
    content: str
    excerpt: Optional[str] = None
    cover_image_url: Optional[str] = None
    category: BlogCategory
    tags: Optional[List[str]] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    status: BlogPostStatus = BlogPostStatus.DRAFT
    scheduled_publish_at: Optional[datetime] = None

class BlogPostUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    excerpt: Optional[str] = None
    cover_image_url: Optional[str] = None
    category: Optional[BlogCategory] = None
    tags: Optional[List[str]] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    status: Optional[BlogPostStatus] = None
    scheduled_publish_at: Optional[datetime] = None

class BlogPostResponse(BaseModel):
    id: int
    doctor_id: int
    doctor_name: str
    doctor_specialization: Optional[str] = None
    doctor_avatar: Optional[str] = None
    title: str
    slug: str
    excerpt: Optional[str]
    content: str
    cover_image_url: Optional[str]
    category: BlogCategory
    tags: List[str]
    meta_title: Optional[str]
    meta_description: Optional[str]
    status: BlogPostStatus
    is_featured: bool
    published_at: Optional[datetime]
    reading_time_minutes: int
    view_count: int
    like_count: int
    comment_count: int
    is_liked: bool = False
    created_at: datetime
    updated_at: datetime

class BlogPostListResponse(BaseModel):
    id: int
    doctor_id: int
    doctor_name: str
    doctor_specialization: Optional[str] = None
    title: str
    slug: str
    excerpt: Optional[str]
    cover_image_url: Optional[str]
    category: BlogCategory
    tags: List[str]
    is_featured: bool
    published_at: Optional[datetime]
    reading_time_minutes: int
    view_count: int
    like_count: int
    comment_count: int

class CommentCreate(BaseModel):
    content: str
    parent_comment_id: Optional[int] = None

class CommentResponse(BaseModel):
    id: int
    post_id: int
    user_id: int
    user_name: str
    user_role: str
    parent_comment_id: Optional[int]
    content: str
    like_count: int
    helpful_count: int
    is_approved: bool
    is_liked: bool = False
    is_marked_helpful: bool = False
    replies: List["CommentResponse"] = []
    created_at: datetime

class BlogStatsResponse(BaseModel):
    total_posts: int
    total_views: int
    total_likes: int
    total_comments: int
    posts_by_category: dict
    top_posts: List[dict]

class PaginatedBlogResponse(BaseModel):
    posts: List[BlogPostListResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ==================== HELPER FUNCTIONS ====================

def generate_slug(title: str) -> str:
    """Generate URL-friendly slug from title"""
    slug = title.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_-]+', '-', slug)
    slug = re.sub(r'^-+|-+$', '', slug)
    return slug

def calculate_reading_time(content: str) -> int:
    """Calculate estimated reading time in minutes"""
    # Strip HTML tags
    text = re.sub(r'<[^>]+>', '', content)
    word_count = len(text.split())
    # Average reading speed: 200 words per minute
    reading_time = max(1, math.ceil(word_count / 200))
    return reading_time

def get_doctor_info(session: Session, doctor_id: int) -> dict:
    """Get doctor information for blog display"""
    user = session.get(User, doctor_id)
    if not user:
        return {"name": "Unknown", "specialization": None, "avatar": None}
    
    profile = session.exec(
        select(DoctorProfile).where(DoctorProfile.user_id == doctor_id)
    ).first()
    
    return {
        "name": user.full_name,
        "specialization": profile.specialization if profile else None,
        "avatar": None  # Add avatar URL if you have it
    }


# ==================== BLOG POST ENDPOINTS ====================

@router.post("/posts", response_model=BlogPostResponse)
def create_blog_post(
    post_data: BlogPostCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(UserRole.DOCTOR))
):
    """Create a new blog post (Doctor only)"""
    # Verify doctor is verified
    doctor_profile = session.exec(
        select(DoctorProfile).where(DoctorProfile.user_id == current_user.id)
    ).first()
    
    if not doctor_profile or not doctor_profile.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only verified doctors can create blog posts"
        )
    
    # Generate unique slug
    base_slug = generate_slug(post_data.title)
    slug = base_slug
    counter = 1
    while session.exec(select(BlogPost).where(BlogPost.slug == slug)).first():
        slug = f"{base_slug}-{counter}"
        counter += 1
    
    # Calculate reading time
    reading_time = calculate_reading_time(post_data.content)
    
    # Set published_at if status is published
    published_at = None
    if post_data.status == BlogPostStatus.PUBLISHED:
        published_at = datetime.utcnow()
    elif post_data.status == BlogPostStatus.PENDING_REVIEW:
        # Requires admin approval
        pass
    
    # Create post
    post = BlogPost(
        doctor_id=current_user.id,
        title=post_data.title,
        slug=slug,
        excerpt=post_data.excerpt or post_data.content[:200] + "...",
        content=post_data.content,
        cover_image_url=post_data.cover_image_url,
        category=post_data.category,
        tags=json.dumps(post_data.tags or []),
        meta_title=post_data.meta_title or post_data.title,
        meta_description=post_data.meta_description or post_data.excerpt,
        status=post_data.status,
        scheduled_publish_at=post_data.scheduled_publish_at,
        published_at=published_at,
        reading_time_minutes=reading_time
    )
    
    session.add(post)
    session.commit()
    session.refresh(post)
    
    doctor_info = get_doctor_info(session, current_user.id)
    
    return BlogPostResponse(
        id=post.id,
        doctor_id=post.doctor_id,
        doctor_name=doctor_info["name"],
        doctor_specialization=doctor_info["specialization"],
        doctor_avatar=doctor_info["avatar"],
        title=post.title,
        slug=post.slug,
        excerpt=post.excerpt,
        content=post.content,
        cover_image_url=post.cover_image_url,
        category=post.category,
        tags=json.loads(post.tags) if post.tags else [],
        meta_title=post.meta_title,
        meta_description=post.meta_description,
        status=post.status,
        is_featured=post.is_featured,
        published_at=post.published_at,
        reading_time_minutes=post.reading_time_minutes,
        view_count=post.view_count,
        like_count=post.like_count,
        comment_count=post.comment_count,
        is_liked=False,
        created_at=post.created_at,
        updated_at=post.updated_at
    )


@router.get("/posts", response_model=PaginatedBlogResponse)
def get_blog_posts(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    category: Optional[BlogCategory] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    doctor_id: Optional[int] = None,
    featured_only: bool = False,
    session: Session = Depends(get_session)
):
    """Get published blog posts (Public)"""
    query = select(BlogPost).where(BlogPost.status == BlogPostStatus.PUBLISHED)
    
    if category:
        query = query.where(BlogPost.category == category)
    
    if tag:
        query = query.where(BlogPost.tags.contains(tag))
    
    if search:
        search_term = f"%{search}%"
        query = query.where(
            or_(
                BlogPost.title.ilike(search_term),
                BlogPost.content.ilike(search_term),
                BlogPost.excerpt.ilike(search_term)
            )
        )
    
    if doctor_id:
        query = query.where(BlogPost.doctor_id == doctor_id)
    
    if featured_only:
        query = query.where(BlogPost.is_featured == True)
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = session.exec(count_query).one()
    
    # Apply pagination and ordering
    query = query.order_by(BlogPost.published_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    posts = session.exec(query).all()
    
    # Build response
    post_list = []
    for post in posts:
        doctor_info = get_doctor_info(session, post.doctor_id)
        post_list.append(BlogPostListResponse(
            id=post.id,
            doctor_id=post.doctor_id,
            doctor_name=doctor_info["name"],
            doctor_specialization=doctor_info["specialization"],
            title=post.title,
            slug=post.slug,
            excerpt=post.excerpt,
            cover_image_url=post.cover_image_url,
            category=post.category,
            tags=json.loads(post.tags) if post.tags else [],
            is_featured=post.is_featured,
            published_at=post.published_at,
            reading_time_minutes=post.reading_time_minutes,
            view_count=post.view_count,
            like_count=post.like_count,
            comment_count=post.comment_count
        ))
    
    return PaginatedBlogResponse(
        posts=post_list,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size)
    )


@router.get("/posts/my", response_model=List[BlogPostListResponse])
def get_my_blog_posts(
    status: Optional[BlogPostStatus] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(UserRole.DOCTOR))
):
    """Get current doctor's blog posts"""
    query = select(BlogPost).where(BlogPost.doctor_id == current_user.id)
    
    if status:
        query = query.where(BlogPost.status == status)
    
    query = query.order_by(BlogPost.created_at.desc())
    posts = session.exec(query).all()
    
    doctor_info = get_doctor_info(session, current_user.id)
    
    return [
        BlogPostListResponse(
            id=post.id,
            doctor_id=post.doctor_id,
            doctor_name=doctor_info["name"],
            doctor_specialization=doctor_info["specialization"],
            title=post.title,
            slug=post.slug,
            excerpt=post.excerpt,
            cover_image_url=post.cover_image_url,
            category=post.category,
            tags=json.loads(post.tags) if post.tags else [],
            is_featured=post.is_featured,
            published_at=post.published_at,
            reading_time_minutes=post.reading_time_minutes,
            view_count=post.view_count,
            like_count=post.like_count,
            comment_count=post.comment_count
        )
        for post in posts
    ]


@router.get("/posts/{slug}", response_model=BlogPostResponse)
def get_blog_post(
    slug: str,
    request: Request,
    session: Session = Depends(get_session),
    current_user: Optional[User] = None
):
    """Get a single blog post by slug (Public)"""
    post = session.exec(
        select(BlogPost).where(BlogPost.slug == slug)
    ).first()
    
    if not post:
        raise HTTPException(status_code=404, detail="Blog post not found")
    
    # Check if published or user is author/admin
    if post.status != BlogPostStatus.PUBLISHED:
        if not current_user or (current_user.id != post.doctor_id and current_user.role != UserRole.ADMIN):
            raise HTTPException(status_code=404, detail="Blog post not found")
    
    # Record view
    view = BlogView(
        post_id=post.id,
        user_id=current_user.id if current_user else None,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    session.add(view)
    
    # Update view count
    post.view_count += 1
    session.add(post)
    session.commit()
    session.refresh(post)
    
    # Check if user liked this post
    is_liked = False
    if current_user:
        like = session.exec(
            select(BlogLike).where(
                and_(BlogLike.post_id == post.id, BlogLike.user_id == current_user.id)
            )
        ).first()
        is_liked = like is not None
    
    doctor_info = get_doctor_info(session, post.doctor_id)
    
    return BlogPostResponse(
        id=post.id,
        doctor_id=post.doctor_id,
        doctor_name=doctor_info["name"],
        doctor_specialization=doctor_info["specialization"],
        doctor_avatar=doctor_info["avatar"],
        title=post.title,
        slug=post.slug,
        excerpt=post.excerpt,
        content=post.content,
        cover_image_url=post.cover_image_url,
        category=post.category,
        tags=json.loads(post.tags) if post.tags else [],
        meta_title=post.meta_title,
        meta_description=post.meta_description,
        status=post.status,
        is_featured=post.is_featured,
        published_at=post.published_at,
        reading_time_minutes=post.reading_time_minutes,
        view_count=post.view_count,
        like_count=post.like_count,
        comment_count=post.comment_count,
        is_liked=is_liked,
        created_at=post.created_at,
        updated_at=post.updated_at
    )


@router.put("/posts/{post_id}", response_model=BlogPostResponse)
def update_blog_post(
    post_id: int,
    post_data: BlogPostUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(UserRole.DOCTOR))
):
    """Update a blog post (Doctor only, own posts)"""
    post = session.get(BlogPost, post_id)
    
    if not post:
        raise HTTPException(status_code=404, detail="Blog post not found")
    
    if post.doctor_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only edit your own posts")
    
    # Update fields
    if post_data.title:
        post.title = post_data.title
        # Regenerate slug if title changed
        base_slug = generate_slug(post_data.title)
        if base_slug != post.slug.rsplit('-', 1)[0]:
            slug = base_slug
            counter = 1
            while session.exec(select(BlogPost).where(and_(BlogPost.slug == slug, BlogPost.id != post_id))).first():
                slug = f"{base_slug}-{counter}"
                counter += 1
            post.slug = slug
    
    if post_data.content:
        post.content = post_data.content
        post.reading_time_minutes = calculate_reading_time(post_data.content)
    
    if post_data.excerpt is not None:
        post.excerpt = post_data.excerpt
    
    if post_data.cover_image_url is not None:
        post.cover_image_url = post_data.cover_image_url
    
    if post_data.category:
        post.category = post_data.category
    
    if post_data.tags is not None:
        post.tags = json.dumps(post_data.tags)
    
    if post_data.meta_title is not None:
        post.meta_title = post_data.meta_title
    
    if post_data.meta_description is not None:
        post.meta_description = post_data.meta_description
    
    if post_data.status:
        # Handle status change
        if post_data.status == BlogPostStatus.PUBLISHED and post.status != BlogPostStatus.PUBLISHED:
            post.published_at = datetime.utcnow()
        post.status = post_data.status
    
    if post_data.scheduled_publish_at is not None:
        post.scheduled_publish_at = post_data.scheduled_publish_at
    
    post.updated_at = datetime.utcnow()
    
    session.add(post)
    session.commit()
    session.refresh(post)
    
    doctor_info = get_doctor_info(session, current_user.id)
    
    return BlogPostResponse(
        id=post.id,
        doctor_id=post.doctor_id,
        doctor_name=doctor_info["name"],
        doctor_specialization=doctor_info["specialization"],
        doctor_avatar=doctor_info["avatar"],
        title=post.title,
        slug=post.slug,
        excerpt=post.excerpt,
        content=post.content,
        cover_image_url=post.cover_image_url,
        category=post.category,
        tags=json.loads(post.tags) if post.tags else [],
        meta_title=post.meta_title,
        meta_description=post.meta_description,
        status=post.status,
        is_featured=post.is_featured,
        published_at=post.published_at,
        reading_time_minutes=post.reading_time_minutes,
        view_count=post.view_count,
        like_count=post.like_count,
        comment_count=post.comment_count,
        is_liked=False,
        created_at=post.created_at,
        updated_at=post.updated_at
    )


@router.delete("/posts/{post_id}")
def delete_blog_post(
    post_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Delete a blog post (Doctor: own posts, Admin: any post)"""
    post = session.get(BlogPost, post_id)
    
    if not post:
        raise HTTPException(status_code=404, detail="Blog post not found")
    
    if post.doctor_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="You can only delete your own posts")
    
    # Delete related records
    session.exec(select(BlogComment).where(BlogComment.post_id == post_id)).all()
    for comment in session.exec(select(BlogComment).where(BlogComment.post_id == post_id)).all():
        session.delete(comment)
    
    for like in session.exec(select(BlogLike).where(BlogLike.post_id == post_id)).all():
        session.delete(like)
    
    for view in session.exec(select(BlogView).where(BlogView.post_id == post_id)).all():
        session.delete(view)
    
    session.delete(post)
    session.commit()
    
    return {"message": "Blog post deleted successfully"}


# ==================== LIKE ENDPOINTS ====================

@router.post("/posts/{post_id}/like")
def like_blog_post(
    post_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Like or unlike a blog post"""
    post = session.get(BlogPost, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Blog post not found")
    
    # Check if already liked
    existing_like = session.exec(
        select(BlogLike).where(
            and_(BlogLike.post_id == post_id, BlogLike.user_id == current_user.id)
        )
    ).first()
    
    if existing_like:
        # Unlike
        session.delete(existing_like)
        post.like_count = max(0, post.like_count - 1)
        session.add(post)
        session.commit()
        return {"liked": False, "like_count": post.like_count}
    else:
        # Like
        like = BlogLike(post_id=post_id, user_id=current_user.id)
        session.add(like)
        post.like_count += 1
        session.add(post)
        session.commit()
        return {"liked": True, "like_count": post.like_count}


# ==================== COMMENT ENDPOINTS ====================

@router.post("/posts/{post_id}/comments", response_model=CommentResponse)
def create_comment(
    post_id: int,
    comment_data: CommentCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Add a comment to a blog post"""
    post = session.get(BlogPost, post_id)
    if not post or post.status != BlogPostStatus.PUBLISHED:
        raise HTTPException(status_code=404, detail="Blog post not found")
    
    # Check parent comment exists if replying
    if comment_data.parent_comment_id:
        parent = session.get(BlogComment, comment_data.parent_comment_id)
        if not parent or parent.post_id != post_id:
            raise HTTPException(status_code=400, detail="Invalid parent comment")
    
    # Simple spam detection
    is_spam = False
    spam_words = ["buy now", "click here", "free money", "congratulations you won"]
    content_lower = comment_data.content.lower()
    for word in spam_words:
        if word in content_lower:
            is_spam = True
            break
    
    comment = BlogComment(
        post_id=post_id,
        user_id=current_user.id,
        parent_comment_id=comment_data.parent_comment_id,
        content=comment_data.content,
        is_approved=not is_spam,
        is_spam=is_spam
    )
    
    session.add(comment)
    
    # Update comment count
    if not is_spam:
        post.comment_count += 1
        session.add(post)
    
    session.commit()
    session.refresh(comment)
    
    user = session.get(User, current_user.id)
    
    return CommentResponse(
        id=comment.id,
        post_id=comment.post_id,
        user_id=comment.user_id,
        user_name=user.full_name,
        user_role=user.role.value,
        parent_comment_id=comment.parent_comment_id,
        content=comment.content,
        like_count=comment.like_count,
        helpful_count=comment.helpful_count,
        is_approved=comment.is_approved,
        is_liked=False,
        is_marked_helpful=False,
        replies=[],
        created_at=comment.created_at
    )


@router.get("/posts/{post_id}/comments", response_model=List[CommentResponse])
def get_comments(
    post_id: int,
    session: Session = Depends(get_session),
    current_user: Optional[User] = None
):
    """Get comments for a blog post (threaded)"""
    post = session.get(BlogPost, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Blog post not found")
    
    # Get top-level comments
    comments = session.exec(
        select(BlogComment).where(
            and_(
                BlogComment.post_id == post_id,
                BlogComment.parent_comment_id == None,
                BlogComment.is_approved == True
            )
        ).order_by(BlogComment.created_at.desc())
    ).all()
    
    def build_comment_response(comment: BlogComment) -> CommentResponse:
        user = session.get(User, comment.user_id)
        
        # Check if current user liked/marked helpful
        is_liked = False
        is_helpful = False
        if current_user:
            like = session.exec(
                select(CommentLike).where(
                    and_(
                        CommentLike.comment_id == comment.id,
                        CommentLike.user_id == current_user.id
                    )
                )
            ).first()
            if like:
                is_liked = not like.is_helpful
                is_helpful = like.is_helpful
        
        # Get replies
        replies = session.exec(
            select(BlogComment).where(
                and_(
                    BlogComment.parent_comment_id == comment.id,
                    BlogComment.is_approved == True
                )
            ).order_by(BlogComment.created_at.asc())
        ).all()
        
        return CommentResponse(
            id=comment.id,
            post_id=comment.post_id,
            user_id=comment.user_id,
            user_name=user.full_name if user else "Unknown",
            user_role=user.role.value if user else "patient",
            parent_comment_id=comment.parent_comment_id,
            content=comment.content,
            like_count=comment.like_count,
            helpful_count=comment.helpful_count,
            is_approved=comment.is_approved,
            is_liked=is_liked,
            is_marked_helpful=is_helpful,
            replies=[build_comment_response(r) for r in replies],
            created_at=comment.created_at
        )
    
    return [build_comment_response(c) for c in comments]


@router.post("/comments/{comment_id}/like")
def like_comment(
    comment_id: int,
    helpful: bool = False,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Like or mark comment as helpful"""
    comment = session.get(BlogComment, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    existing = session.exec(
        select(CommentLike).where(
            and_(
                CommentLike.comment_id == comment_id,
                CommentLike.user_id == current_user.id
            )
        )
    ).first()
    
    if existing:
        # Toggle or remove
        if existing.is_helpful == helpful:
            # Remove
            session.delete(existing)
            if helpful:
                comment.helpful_count = max(0, comment.helpful_count - 1)
            else:
                comment.like_count = max(0, comment.like_count - 1)
            session.add(comment)
            session.commit()
            return {"liked": False, "helpful": False}
        else:
            # Switch type
            if existing.is_helpful:
                comment.helpful_count = max(0, comment.helpful_count - 1)
                comment.like_count += 1
            else:
                comment.like_count = max(0, comment.like_count - 1)
                comment.helpful_count += 1
            existing.is_helpful = helpful
            session.add(existing)
            session.add(comment)
            session.commit()
            return {"liked": not helpful, "helpful": helpful}
    else:
        # Add new
        like = CommentLike(
            comment_id=comment_id,
            user_id=current_user.id,
            is_helpful=helpful
        )
        session.add(like)
        if helpful:
            comment.helpful_count += 1
        else:
            comment.like_count += 1
        session.add(comment)
        session.commit()
        return {"liked": not helpful, "helpful": helpful}


@router.post("/comments/{comment_id}/report")
def report_comment(
    comment_id: int,
    reason: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Report a comment"""
    comment = session.get(BlogComment, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    comment.is_reported = True
    comment.report_reason = reason
    session.add(comment)
    session.commit()
    
    return {"message": "Comment reported successfully"}


@router.delete("/comments/{comment_id}")
def delete_comment(
    comment_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Delete a comment (own comments, post author, or admin)"""
    comment = session.get(BlogComment, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    post = session.get(BlogPost, comment.post_id)
    
    # Check permission
    can_delete = (
        comment.user_id == current_user.id or
        (post and post.doctor_id == current_user.id) or
        current_user.role == UserRole.ADMIN
    )
    
    if not can_delete:
        raise HTTPException(status_code=403, detail="Not authorized to delete this comment")
    
    # Delete replies first
    for reply in session.exec(select(BlogComment).where(BlogComment.parent_comment_id == comment_id)).all():
        session.delete(reply)
    
    # Update comment count
    if post and comment.is_approved:
        post.comment_count = max(0, post.comment_count - 1)
        session.add(post)
    
    session.delete(comment)
    session.commit()
    
    return {"message": "Comment deleted successfully"}


# ==================== FOLLOW ENDPOINTS ====================

@router.post("/doctors/{doctor_id}/follow")
def follow_doctor(
    doctor_id: int,
    notify_email: bool = True,
    notify_whatsapp: bool = False,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Follow a doctor for blog updates"""
    # Verify doctor exists
    doctor = session.get(User, doctor_id)
    if not doctor or doctor.role != UserRole.DOCTOR:
        raise HTTPException(status_code=404, detail="Doctor not found")
    
    if doctor_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot follow yourself")
    
    # Check existing follow
    existing = session.exec(
        select(BlogFollower).where(
            and_(
                BlogFollower.doctor_id == doctor_id,
                BlogFollower.follower_id == current_user.id
            )
        )
    ).first()
    
    if existing:
        # Unfollow
        session.delete(existing)
        session.commit()
        return {"following": False}
    else:
        # Follow
        follow = BlogFollower(
            doctor_id=doctor_id,
            follower_id=current_user.id,
            notify_email=notify_email,
            notify_whatsapp=notify_whatsapp
        )
        session.add(follow)
        session.commit()
        return {"following": True}


@router.get("/doctors/{doctor_id}/followers/count")
def get_follower_count(
    doctor_id: int,
    session: Session = Depends(get_session)
):
    """Get follower count for a doctor"""
    count = session.exec(
        select(func.count()).select_from(BlogFollower).where(BlogFollower.doctor_id == doctor_id)
    ).one()
    return {"count": count}


# ==================== ADMIN ENDPOINTS ====================

@router.get("/admin/pending", response_model=List[BlogPostListResponse])
def get_pending_posts(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(UserRole.ADMIN))
):
    """Get posts pending review (Admin only)"""
    posts = session.exec(
        select(BlogPost).where(BlogPost.status == BlogPostStatus.PENDING_REVIEW)
        .order_by(BlogPost.created_at.asc())
    ).all()
    
    return [
        BlogPostListResponse(
            id=post.id,
            doctor_id=post.doctor_id,
            doctor_name=get_doctor_info(session, post.doctor_id)["name"],
            doctor_specialization=get_doctor_info(session, post.doctor_id)["specialization"],
            title=post.title,
            slug=post.slug,
            excerpt=post.excerpt,
            cover_image_url=post.cover_image_url,
            category=post.category,
            tags=json.loads(post.tags) if post.tags else [],
            is_featured=post.is_featured,
            published_at=post.published_at,
            reading_time_minutes=post.reading_time_minutes,
            view_count=post.view_count,
            like_count=post.like_count,
            comment_count=post.comment_count
        )
        for post in posts
    ]


@router.post("/admin/posts/{post_id}/approve")
def approve_post(
    post_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(UserRole.ADMIN))
):
    """Approve a pending blog post"""
    post = session.get(BlogPost, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Blog post not found")
    
    post.status = BlogPostStatus.PUBLISHED
    post.published_at = datetime.utcnow()
    post.moderated_by = current_user.id
    post.moderated_at = datetime.utcnow()
    
    session.add(post)
    session.commit()
    
    # TODO: Notify followers
    
    return {"message": "Blog post approved and published"}


@router.post("/admin/posts/{post_id}/reject")
def reject_post(
    post_id: int,
    reason: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(UserRole.ADMIN))
):
    """Reject a pending blog post"""
    post = session.get(BlogPost, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Blog post not found")
    
    post.status = BlogPostStatus.REJECTED
    post.rejection_reason = reason
    post.moderated_by = current_user.id
    post.moderated_at = datetime.utcnow()
    
    session.add(post)
    session.commit()
    
    return {"message": "Blog post rejected"}


@router.post("/admin/posts/{post_id}/feature")
def toggle_featured(
    post_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(UserRole.ADMIN))
):
    """Toggle featured status of a blog post"""
    post = session.get(BlogPost, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Blog post not found")
    
    post.is_featured = not post.is_featured
    session.add(post)
    session.commit()
    
    return {"featured": post.is_featured}


@router.get("/admin/reported-comments", response_model=List[CommentResponse])
def get_reported_comments(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(UserRole.ADMIN))
):
    """Get reported comments for moderation"""
    comments = session.exec(
        select(BlogComment).where(BlogComment.is_reported == True)
        .order_by(BlogComment.created_at.desc())
    ).all()
    
    result = []
    for comment in comments:
        user = session.get(User, comment.user_id)
        result.append(CommentResponse(
            id=comment.id,
            post_id=comment.post_id,
            user_id=comment.user_id,
            user_name=user.full_name if user else "Unknown",
            user_role=user.role.value if user else "patient",
            parent_comment_id=comment.parent_comment_id,
            content=comment.content,
            like_count=comment.like_count,
            helpful_count=comment.helpful_count,
            is_approved=comment.is_approved,
            replies=[],
            created_at=comment.created_at
        ))
    
    return result


@router.get("/admin/stats", response_model=BlogStatsResponse)
def get_blog_stats(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(UserRole.ADMIN))
):
    """Get blog analytics (Admin only)"""
    total_posts = session.exec(
        select(func.count()).select_from(BlogPost)
    ).one()
    
    total_views = session.exec(
        select(func.sum(BlogPost.view_count)).select_from(BlogPost)
    ).one() or 0
    
    total_likes = session.exec(
        select(func.sum(BlogPost.like_count)).select_from(BlogPost)
    ).one() or 0
    
    total_comments = session.exec(
        select(func.count()).select_from(BlogComment)
    ).one()
    
    # Posts by category
    category_stats = {}
    for category in BlogCategory:
        count = session.exec(
            select(func.count()).select_from(BlogPost)
            .where(BlogPost.category == category)
        ).one()
        category_stats[category.value] = count
    
    # Top posts by views
    top_posts = session.exec(
        select(BlogPost)
        .where(BlogPost.status == BlogPostStatus.PUBLISHED)
        .order_by(BlogPost.view_count.desc())
        .limit(5)
    ).all()
    
    return BlogStatsResponse(
        total_posts=total_posts,
        total_views=total_views,
        total_likes=total_likes,
        total_comments=total_comments,
        posts_by_category=category_stats,
        top_posts=[
            {
                "id": p.id,
                "title": p.title,
                "views": p.view_count,
                "likes": p.like_count
            }
            for p in top_posts
        ]
    )


# ==================== CATEGORY & TAG ENDPOINTS ====================

@router.get("/categories")
def get_categories():
    """Get all blog categories"""
    return [{"value": c.value, "label": c.value.replace("_", " ").title()} for c in BlogCategory]


@router.get("/tags")
def get_popular_tags(
    limit: int = 20,
    session: Session = Depends(get_session)
):
    """Get popular tags"""
    posts = session.exec(
        select(BlogPost).where(BlogPost.status == BlogPostStatus.PUBLISHED)
    ).all()
    
    tag_counts = {}
    for post in posts:
        tags = json.loads(post.tags) if post.tags else []
        for tag in tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    
    sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:limit]
    return [{"tag": tag, "count": count} for tag, count in sorted_tags]


# ==================== DOCTOR BLOG STATS ====================

@router.get("/doctors/me/stats")
def get_my_blog_stats(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get blog statistics for the current logged-in doctor"""
    if current_user.role != "doctor":
        raise HTTPException(status_code=403, detail="Only doctors can access their blog stats")
    
    # Get total posts count (all statuses)
    total_posts = session.exec(
        select(func.count()).select_from(BlogPost)
        .where(BlogPost.doctor_id == current_user.id)
    ).one()
    
    # Get total views
    total_views = session.exec(
        select(func.sum(BlogPost.view_count)).select_from(BlogPost)
        .where(BlogPost.doctor_id == current_user.id)
    ).one() or 0
    
    # Get total likes
    total_likes = session.exec(
        select(func.sum(BlogPost.like_count)).select_from(BlogPost)
        .where(BlogPost.doctor_id == current_user.id)
    ).one() or 0
    
    # Get total comments
    post_ids = session.exec(
        select(BlogPost.id).where(BlogPost.doctor_id == current_user.id)
    ).all()
    
    total_comments = 0
    if post_ids:
        total_comments = session.exec(
            select(func.count()).select_from(BlogComment)
            .where(BlogComment.post_id.in_(post_ids))
        ).one()
    
    # Get follower count
    followers_count = session.exec(
        select(func.count()).select_from(BlogFollower)
        .where(BlogFollower.doctor_id == current_user.id)
    ).one()
    
    return {
        "total_posts": total_posts,
        "total_views": total_views,
        "total_likes": total_likes,
        "total_comments": total_comments,
        "followers_count": followers_count
    }


@router.get("/doctors/{doctor_id}/stats")
def get_doctor_blog_stats(
    doctor_id: int,
    session: Session = Depends(get_session)
):
    """Get blog statistics for a specific doctor"""
    post_count = session.exec(
        select(func.count()).select_from(BlogPost)
        .where(and_(BlogPost.doctor_id == doctor_id, BlogPost.status == BlogPostStatus.PUBLISHED))
    ).one()
    
    total_views = session.exec(
        select(func.sum(BlogPost.view_count)).select_from(BlogPost)
        .where(and_(BlogPost.doctor_id == doctor_id, BlogPost.status == BlogPostStatus.PUBLISHED))
    ).one() or 0
    
    total_likes = session.exec(
        select(func.sum(BlogPost.like_count)).select_from(BlogPost)
        .where(and_(BlogPost.doctor_id == doctor_id, BlogPost.status == BlogPostStatus.PUBLISHED))
    ).one() or 0
    
    follower_count = session.exec(
        select(func.count()).select_from(BlogFollower)
        .where(BlogFollower.doctor_id == doctor_id)
    ).one()
    
    return {
        "post_count": post_count,
        "total_views": total_views,
        "total_likes": total_likes,
        "follower_count": follower_count
    }
