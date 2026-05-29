import json
from datetime import datetime, timezone
from typing import Any

from bilibili_api import Credential, article, user
from bilibili_api.exceptions import ResponseCodeException

from app.bilibili.schemas import DYNAMIC_TYPE_DISPLAY, VIDEO_TYPE_DISPLAY


class BilibiliClient:
    def __init__(self, credentials: dict, auth_type: str) -> None:
        self.auth_type = auth_type
        self.credentials = credentials
        self.credential = self._create_credential(credentials)

    def _create_credential(self, credentials: dict) -> Credential:
        if self.auth_type == "cookie":
            cookie_dict = self._parse_cookie(credentials["cookie"])
            return Credential(
                sessdata=cookie_dict.get("SESSDATA"),
                bili_jct=cookie_dict.get("bili_jct"),
                buvid3=cookie_dict.get("buvid3"),
            )
        return Credential(
            sessdata=credentials.get("sessdata"),
            bili_jct=credentials.get("bili_jct"),
            buvid3=credentials.get("buvid3"),
        )

    async def verify_credentials(self) -> bool:
        try:
            uid = self.credentials.get("dedeuserid") or self.credentials.get("DedeUserID")
            if not uid:
                return False
            u = user.User(uid=int(uid), credential=self.credential)
            await u.get_user_info()
            return True
        except ResponseCodeException:
            return False

    async def get_user_info(self, uid: str) -> dict[str, Any]:
        u = user.User(uid=int(uid), credential=self.credential)
        info = await u.get_user_info()
        relation_info = await u.get_relation_info()
        return {
            "uid": uid,
            "name": info["name"],
            "avatar": info["face"],
            "follower_count": info.get("follower") or relation_info.get("follower", 0),
            "description": info.get("sign", ""),
        }

    async def get_current_account_profile(self) -> dict[str, Any]:
        uid = self.credentials.get("dedeuserid") or self.credentials.get("DedeUserID")
        if not uid:
            return {}
        return await self.get_user_info(str(uid))

    async def check_uploader_exists(self, uid: str) -> bool:
        try:
            u = user.User(uid=int(uid), credential=self.credential)
            await u.get_user_info()
            return True
        except ResponseCodeException as e:
            if e.code == -404:
                return False
            raise

    async def get_user_videos(
        self, uid: str, page: int = 1, page_size: int = 50
    ) -> list[dict[str, Any]]:
        u = user.User(uid=int(uid), credential=self.credential)
        videos = await u.get_videos(pn=page, ps=page_size)
        return [self._transform_video_data(v) for v in videos["list"]["vlist"]]

    async def get_user_dynamics(
        self, uid: str, offset: str | None = None
    ) -> list[dict[str, Any]]:
        u = user.User(uid=int(uid), credential=self.credential)
        dynamics = await u.get_dynamics(offset=offset)
        return [self._transform_dynamic_data(d) for d in dynamics.get("cards") or []]

    async def get_user_articles(
        self, uid: str, page: int = 1
    ) -> list[dict[str, Any]]:
        u = user.User(uid=int(uid), credential=self.credential)
        articles = await u.get_articles(pn=page)
        results = []
        for item in articles.get("articles") or []:
            results.append(
                self._transform_article_data(
                    item,
                    await self._fetch_article_full_content(item),
                )
            )
        return results

    def _transform_video_data(self, raw: dict) -> dict[str, Any]:
        return {
            "resource_type": "video",
            "resource_id": raw["bvid"],
            "title": raw["title"],
            "cover_url": raw["pic"],
            "summary": raw["description"][:200],
            "full_content": raw["description"],
            "published_at": datetime.fromtimestamp(raw["created"], timezone.utc),
            "resource_meta": {
                "bvid": raw["bvid"],
                "aid": raw["aid"],
                "video_type": raw.get("copyright", 1),
                "video_type_display": VIDEO_TYPE_DISPLAY.get(raw.get("copyright", 1), "未知"),
                "play_count": raw["play"],
                "like_count": raw.get("like", 0),
                "coin_count": raw.get("coin", 0),
                "duration": raw["length"],
                "url": f"https://www.bilibili.com/video/{raw['bvid']}",
            },
        }

    def _transform_dynamic_data(self, raw: dict) -> dict[str, Any]:
        card = raw["card"]
        if isinstance(card, str):
            card = json.loads(card)
        dynamic_type = raw["desc"]["type"]
        content = self._extract_dynamic_content(card)
        return {
            "resource_type": "dynamic",
            "resource_id": str(raw["desc"]["dynamic_id"]),
            "title": card.get("title", "动态"),
            "cover_url": card.get("pic", ""),
            "summary": content[:200],
            "full_content": content,
            "published_at": datetime.fromtimestamp(raw["desc"]["timestamp"], timezone.utc),
            "attachments": self._extract_dynamic_attachments(card),
            "resource_meta": {
                "dynamic_id": raw["desc"]["dynamic_id"],
                "dynamic_type": dynamic_type,
                "dynamic_type_display": DYNAMIC_TYPE_DISPLAY.get(dynamic_type, "未知"),
                "like_count": raw["desc"].get("like", 0),
                "url": f"https://t.bilibili.com/{raw['desc']['dynamic_id']}",
            },
        }

    async def _fetch_article_full_content(self, raw: dict) -> str:
        cvid = int(raw["id"])
        if self._is_note_article(raw):
            try:
                note = article.Note(
                    cvid=cvid,
                    note_type=article.NoteType.PUBLIC,
                    credential=self.credential,
                )
                await note.fetch_content()
                return note.markdown()
            except Exception:
                pass

        return raw.get("summary", "")

    def _is_note_article(self, raw: dict) -> bool:
        category = raw.get("category") or {}
        return category.get("id") in {41, 42}

    def _transform_article_data(self, raw: dict, full_content: str | None = None) -> dict[str, Any]:
        return {
            "resource_type": "article",
            "resource_id": str(raw["id"]),
            "title": raw["title"],
            "cover_url": raw["image_urls"][0] if raw["image_urls"] else "",
            "summary": raw["summary"],
            "full_content": full_content or raw["summary"],
            "published_at": datetime.fromtimestamp(raw["publish_time"], timezone.utc),
            "resource_meta": {
                "article_id": raw["id"],
                "view_count": raw.get("view", 0),
                "like_count": raw.get("like", 0),
                "url": f"https://www.bilibili.com/read/cv{raw['id']}",
            },
        }

    def _extract_dynamic_content(self, card: dict) -> str:
        item = card.get("item") or {}
        return (
            card.get("content")
            or card.get("dynamic")
            or item.get("description")
            or item.get("content")
            or ""
        )

    def _extract_dynamic_attachments(self, card: dict) -> dict[str, Any]:
        attachments: dict[str, Any] = {"images": [], "documents": []}
        if "pictures" in card:
            attachments["images"] = [p["img_src"] for p in card["pictures"] or []]
        elif "pictures" in (card.get("item") or {}):
            attachments["images"] = [p["img_src"] for p in card["item"]["pictures"] or []]
        return attachments

    def _parse_cookie(self, cookie_str: str) -> dict[str, str]:
        cookie_dict: dict[str, str] = {}
        for item in cookie_str.split(";"):
            if "=" in item:
                key, value = item.strip().split("=", 1)
                cookie_dict[key] = value
        return cookie_dict
