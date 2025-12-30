"""
Instagram Scraper - Core scraping functionality
Handles extraction of public Instagram data using instaloader
"""

import asyncio
import logging
from typing import List, Dict, Any, Callable, Optional
from datetime import datetime
import re
from pathlib import Path
import instaloader
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class InstagramScraper:
    """
    Core Instagram scraper using instaloader library
    Extracts public data from posts, profiles, hashtags, and places
    """
    
    def __init__(self, storage_manager):
        self.storage_manager = storage_manager
        self.loader = instaloader.Instaloader(
            download_pictures=False,
            download_videos=False,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False,
            quiet=True
        )
    
    async def scrape_batch(
        self,
        job_id: str,
        urls: List[str],
        scrape_type: str,
        include_media: bool = True,
        include_comments: bool = True,
        callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict[str, Any]:
        """
        Scrape multiple URLs in batch
        """
        results = []
        total = len(urls)
        
        for idx, url in enumerate(urls):
            try:
                logger.info(f"Scraping {idx + 1}/{total}: {url}")
                
                data = await self._scrape_url(
                    url=url,
                    scrape_type=scrape_type,
                    include_media=include_media,
                    include_comments=include_comments
                )
                
                if data:
                    # Download media files if requested
                    if include_media and 'media' in data:
                        data['media'] = await self._download_media_files(
                            job_id=job_id,
                            media_list=data['media'],
                            post_id=data.get('shortcode', data.get('username', 'unknown'))
                        )
                    
                    # Save to storage
                    self.storage_manager.save_scraped_data(job_id, data)
                    results.append(data)
                
                # Update progress
                if callback:
                    callback(idx + 1, total)
                
                # Rate limiting
                await asyncio.sleep(2)
            
            except Exception as e:
                logger.error(f"Error scraping {url}: {str(e)}")
                results.append({
                    "url": url,
                    "error": str(e),
                    "scraped_at": datetime.now().isoformat()
                })
        
        return {"results": results, "total": len(results)}
    
    async def _scrape_url(
        self,
        url: str,
        scrape_type: str,
        include_media: bool,
        include_comments: bool
    ) -> Optional[Dict[str, Any]]:
        """
        Scrape a single Instagram URL
        """
        try:
            # Extract shortcode/username from URL
            identifier = self._extract_identifier(url, scrape_type)
            
            if scrape_type == "post":
                return await self._scrape_post(identifier, include_media, include_comments)
            elif scrape_type == "profile":
                return await self._scrape_profile(identifier, include_media)
            elif scrape_type == "hashtag":
                return await self._scrape_hashtag(identifier, include_media)
            elif scrape_type == "place":
                return await self._scrape_place(identifier, include_media)
            
        except Exception as e:
            logger.error(f"Error in _scrape_url: {str(e)}")
            raise
    
    def _extract_identifier(self, url: str, scrape_type: str) -> str:
        """
        Extract identifier (shortcode, username, etc.) from Instagram URL
        """
        parsed = urlparse(url)
        path = parsed.path.strip('/')
        
        if scrape_type == "post":
            # Extract shortcode from /p/SHORTCODE/ or /reel/SHORTCODE/
            match = re.search(r'(?:p|reel)/([A-Za-z0-9_-]+)', path)
            if match:
                return match.group(1)
        
        elif scrape_type == "profile":
            # Extract username
            match = re.search(r'^([A-Za-z0-9._]+)/?$', path)
            if match:
                return match.group(1)
        
        elif scrape_type == "hashtag":
            # Extract hashtag
            match = re.search(r'explore/tags/([^/]+)', path)
            if match:
                return match.group(1)
        
        elif scrape_type == "place":
            # Extract place ID
            match = re.search(r'explore/locations/([0-9]+)', path)
            if match:
                return match.group(1)
        
        raise ValueError(f"Could not extract identifier from URL: {url}")
    
    async def _scrape_post(
        self,
        shortcode: str,
        include_media: bool,
        include_comments: bool
    ) -> Dict[str, Any]:
        """
        Scrape a single Instagram post
        """
        try:
            # Get post using instaloader
            post = instaloader.Post.from_shortcode(self.loader.context, shortcode)
            
            data = {
                "type": "post",
                "shortcode": shortcode,
                "url": f"https://www.instagram.com/p/{shortcode}/",
                "caption": post.caption if post.caption else "",
                "likes": post.likes,
                "comments_count": post.comments,
                "timestamp": post.date_utc.isoformat(),
                "is_video": post.is_video,
                "owner": {
                    "username": post.owner_username,
                    "user_id": post.owner_id
                },
                "location": {
                    "name": post.location.name if post.location else None,
                    "id": post.location.id if post.location else None
                } if post.location else None,
                "hashtags": list(post.caption_hashtags) if post.caption else [],
                "mentions": list(post.caption_mentions) if post.caption else [],
                "scraped_at": datetime.now().isoformat()
            }
            
            # Add media URLs
            if include_media:
                if post.is_video:
                    data["media"] = [{
                        "type": "video",
                        "url": post.video_url,
                        "thumbnail": post.url
                    }]
                else:
                    # Handle multiple images (carousel)
                    if post.typename == "GraphSidecar":
                        data["media"] = [
                            {"type": "image", "url": node.display_url}
                            for node in post.get_sidecar_nodes()
                        ]
                    else:
                        data["media"] = [{
                            "type": "image",
                            "url": post.url
                        }]
            
            # Add comments
            if include_comments:
                comments = []
                try:
                    for comment in post.get_comments():
                        comments.append({
                            "user": comment.owner.username,
                            "text": comment.text,
                            "created_at": comment.created_at_utc.isoformat(),
                            "likes": comment.likes_count
                        })
                        # Limit to 50 comments to avoid rate limits
                        if len(comments) >= 50:
                            break
                except Exception as e:
                    logger.warning(f"Could not fetch comments: {str(e)}")
                
                data["comments"] = comments
            
            return data
        
        except Exception as e:
            logger.error(f"Error scraping post {shortcode}: {str(e)}")
            raise
    
    async def _scrape_profile(
        self,
        username: str,
        include_media: bool
    ) -> Dict[str, Any]:
        """
        Scrape an Instagram profile
        """
        try:
            profile = instaloader.Profile.from_username(self.loader.context, username)
            
            data = {
                "type": "profile",
                "username": profile.username,
                "full_name": profile.full_name,
                "user_id": profile.userid,
                "biography": profile.biography,
                "external_url": profile.external_url,
                "followers": profile.followers,
                "following": profile.followees,
                "post_count": profile.mediacount,
                "is_verified": profile.is_verified,
                "is_private": profile.is_private,
                "profile_pic_url": profile.profile_pic_url,
                "scraped_at": datetime.now().isoformat()
            }
            
            # Add recent posts
            if include_media and not profile.is_private:
                recent_posts = []
                try:
                    for post in profile.get_posts():
                        recent_posts.append({
                            "shortcode": post.shortcode,
                            "url": f"https://www.instagram.com/p/{post.shortcode}/",
                            "likes": post.likes,
                            "comments": post.comments,
                            "timestamp": post.date_utc.isoformat()
                        })
                        # Limit to 12 recent posts
                        if len(recent_posts) >= 12:
                            break
                except Exception as e:
                    logger.warning(f"Could not fetch posts: {str(e)}")
                
                data["recent_posts"] = recent_posts
            
            return data
        
        except Exception as e:
            logger.error(f"Error scraping profile {username}: {str(e)}")
            raise
    
    async def _scrape_hashtag(
        self,
        hashtag: str,
        include_media: bool
    ) -> Dict[str, Any]:
        """
        Scrape an Instagram hashtag
        """
        try:
            hashtag_obj = instaloader.Hashtag.from_name(self.loader.context, hashtag)
            
            data = {
                "type": "hashtag",
                "name": hashtag,
                "post_count": hashtag_obj.mediacount,
                "scraped_at": datetime.now().isoformat()
            }
            
            # Add recent posts
            if include_media:
                recent_posts = []
                try:
                    for post in hashtag_obj.get_posts():
                        recent_posts.append({
                            "shortcode": post.shortcode,
                            "url": f"https://www.instagram.com/p/{post.shortcode}/",
                            "caption": post.caption[:200] if post.caption else "",
                            "likes": post.likes,
                            "comments": post.comments,
                            "timestamp": post.date_utc.isoformat(),
                            "owner": post.owner_username
                        })
                        # Limit to 20 posts
                        if len(recent_posts) >= 20:
                            break
                except Exception as e:
                    logger.warning(f"Could not fetch posts: {str(e)}")
                
                data["recent_posts"] = recent_posts
            
            return data
        
        except Exception as e:
            logger.error(f"Error scraping hashtag {hashtag}: {str(e)}")
            raise
    
    async def _scrape_place(
        self,
        place_id: str,
        include_media: bool
    ) -> Dict[str, Any]:
        """
        Scrape an Instagram place/location
        Note: Place scraping requires additional logic
        """
        # This is a placeholder - full implementation would require
        # more sophisticated querying
        return {
            "type": "place",
            "place_id": place_id,
            "scraped_at": datetime.now().isoformat(),
            "note": "Place scraping requires additional implementation"
        }
    
    async def _download_media_files(
        self,
        job_id: str,
        media_list: List[Dict[str, str]],
        post_id: str
    ) -> List[Dict[str, str]]:
        """
        Download media files and update URLs with local paths
        """
        import aiohttp
        
        updated_media = []
        
        for idx, media_item in enumerate(media_list):
            try:
                media_url = media_item.get('url')
                media_type = media_item.get('type', 'image')
                
                if not media_url:
                    updated_media.append(media_item)
                    continue
                
                # Generate filename
                extension = 'mp4' if media_type == 'video' else 'jpg'
                filename = f"{post_id}_{idx + 1}.{extension}"
                
                # Download file
                local_path = await self.storage_manager.download_media(
                    job_id=job_id,
                    media_url=media_url,
                    filename=filename
                )
                
                # Update media item with local path
                media_item['local_path'] = str(local_path.relative_to(self.storage_manager.get_job_dir(job_id)))
                media_item['downloaded'] = True
                
                logger.info(f"Downloaded {media_type}: {filename}")
                
            except Exception as e:
                logger.error(f"Error downloading media {idx}: {str(e)}")
                media_item['download_error'] = str(e)
                media_item['downloaded'] = False
            
            updated_media.append(media_item)
        
        return updated_media