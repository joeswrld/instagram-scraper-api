"""
Usage Tracker - Track API usage and calculate billing
Implements subscription-based pricing with included posts
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from threading import Lock
import uuid

logger = logging.getLogger(__name__)


@dataclass
class UsageRecord:
    """Single usage record"""
    record_id: str
    api_key: str
    user_id: str
    job_id: str
    timestamp: datetime
    posts_scraped: int
    comments_included: bool
    media_included: bool
    storage_used_mb: float
    cost_usd: float
    pricing_tier: str
    is_overage: bool = False  # True if beyond included posts
    
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['timestamp'] = self.timestamp.isoformat()
        return d


@dataclass
class UserAccount:
    """User account with subscription billing"""
    user_id: str
    email: str
    api_keys: list
    pricing_tier: str = "professional"  # starter, professional, enterprise
    total_posts_scraped: int = 0
    total_spent: float = 0.0
    current_month_posts: int = 0
    current_month_cost: float = 0.0
    current_month_overage_cost: float = 0.0  # Cost beyond included posts
    credits_balance: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    billing_cycle_start: datetime = field(default_factory=datetime.now)
    is_active: bool = True
    spending_limit: Optional[float] = None
    subscription_paid: bool = True  # False if payment failed
    
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['created_at'] = self.created_at.isoformat()
        d['billing_cycle_start'] = self.billing_cycle_start.isoformat()
        return d


class PricingTiers:
    """Subscription pricing with included posts"""
    
    TIERS = {
        "starter": {
            "base_price": 0.01,              # Overage rate per post
            "name": "Starter",
            "monthly_cost": 10.00,           # Fixed monthly subscription
            "included_posts": 1000,          # FREE posts included
            "concurrent_jobs": 5,
            "description": "Perfect for small businesses"
        },
        "professional": {
            "base_price": 0.0075,
            "name": "Professional",
            "monthly_cost": 37.50,
            "included_posts": 5000,          # FREE posts included
            "concurrent_jobs": 20,
            "description": "Best for agencies & marketers"
        },
        "enterprise": {
            "base_price": 0.005,
            "name": "Enterprise",
            "monthly_cost": 100.00,
            "included_posts": 20000,         # FREE posts included
            "concurrent_jobs": 999,
            "description": "For large-scale operations"
        }
    }
    
    MULTIPLIERS = {
        "comments": 1.25,  # 25% increase
        "media": 1.50      # 50% increase
    }
    
    # Volume discounts for overage (posts beyond included)
    VOLUME_DISCOUNTS = [
        {"threshold": 10000, "discount": 0.90},   # 10% off overage
        {"threshold": 50000, "discount": 0.85},   # 15% off overage
        {"threshold": 100000, "discount": 0.75},  # 25% off overage
    ]
    
    @classmethod
    def calculate_cost(
        cls,
        num_posts: int,
        tier: str,
        include_comments: bool,
        include_media: bool,
        current_month_posts: int = 0
    ) -> Dict[str, float]:
        """
        Calculate cost with subscription model
        Returns: {
            "subscription": monthly_cost,
            "overage": overage_cost,
            "total": total_cost,
            "included_used": posts_within_limit,
            "overage_posts": posts_beyond_limit
        }
        """
        if tier not in cls.TIERS:
            tier = "professional"
        
        tier_info = cls.TIERS[tier]
        monthly_cost = tier_info["monthly_cost"]
        included_posts = tier_info["included_posts"]
        overage_rate = tier_info["base_price"]
        
        # Apply feature multipliers to overage rate
        if include_comments:
            overage_rate *= cls.MULTIPLIERS["comments"]
        if include_media:
            overage_rate *= cls.MULTIPLIERS["media"]
        
        # Calculate how many posts are within included limit
        posts_within_limit = min(num_posts, max(0, included_posts - current_month_posts))
        overage_posts = num_posts - posts_within_limit
        
        # Calculate overage cost
        overage_cost = 0.0
        if overage_posts > 0:
            overage_cost = overage_posts * overage_rate
            
            # Apply volume discount to overage
            total_overage = (current_month_posts - included_posts) + overage_posts
            if total_overage > 0:
                for discount_rule in cls.VOLUME_DISCOUNTS:
                    if total_overage >= discount_rule["threshold"]:
                        overage_cost *= discount_rule["discount"]
                        break
        
        return {
            "subscription": monthly_cost,
            "overage": round(overage_cost, 4),
            "total": round(monthly_cost + overage_cost, 4),
            "included_used": posts_within_limit,
            "overage_posts": overage_posts
        }


class UsageTracker:
    """
    Track API usage with subscription billing model
    Thread-safe usage tracking
    """
    
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.usage_dir = self.data_dir / "usage"
        self.usage_dir.mkdir(exist_ok=True)
        
        self.accounts: Dict[str, UserAccount] = {}
        self.api_key_to_user: Dict[str, str] = {}
        self.lock = Lock()
        
        self._load_accounts()
    
    def _load_accounts(self):
        """Load user accounts from disk"""
        accounts_file = self.usage_dir / "accounts.json"
        if accounts_file.exists():
            try:
                with open(accounts_file, 'r') as f:
                    data = json.load(f)
                    for user_id, account_data in data.items():
                        account_data['created_at'] = datetime.fromisoformat(account_data['created_at'])
                        account_data['billing_cycle_start'] = datetime.fromisoformat(account_data['billing_cycle_start'])
                        self.accounts[user_id] = UserAccount(**account_data)
                        
                        # Build API key lookup
                        for api_key in self.accounts[user_id].api_keys:
                            self.api_key_to_user[api_key] = user_id
                
                logger.info(f"Loaded {len(self.accounts)} user accounts")
            except Exception as e:
                logger.error(f"Error loading accounts: {e}")
    
    def _save_accounts(self):
        """Save user accounts to disk"""
        accounts_file = self.usage_dir / "accounts.json"
        try:
            data = {
                user_id: account.to_dict()
                for user_id, account in self.accounts.items()
            }
            with open(accounts_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving accounts: {e}")
    
    def create_account(
        self,
        email: str,
        api_keys: list,
        pricing_tier: str = "professional",
        spending_limit: Optional[float] = None
    ) -> UserAccount:
        """Create new user account"""
        with self.lock:
            user_id = str(uuid.uuid4())
            
            account = UserAccount(
                user_id=user_id,
                email=email,
                api_keys=api_keys,
                pricing_tier=pricing_tier,
                spending_limit=spending_limit
            )
            
            self.accounts[user_id] = account
            
            # Map API keys to user
            for api_key in api_keys:
                self.api_key_to_user[api_key] = user_id
            
            self._save_accounts()
            logger.info(f"Created account for {email} with tier {pricing_tier}")
            
            return account
    
    def get_user_from_api_key(self, api_key: str) -> Optional[UserAccount]:
        """Get user account from API key"""
        with self.lock:
            user_id = self.api_key_to_user.get(api_key)
            if user_id:
                return self.accounts.get(user_id)
            return None
    
    def record_usage(
        self,
        api_key: str,
        job_id: str,
        num_posts: int,
        include_comments: bool,
        include_media: bool,
        storage_used_mb: float = 0.0
    ) -> UsageRecord:
        """Record usage with subscription model"""
        with self.lock:
            # Get user account
            account = self.get_user_from_api_key(api_key)
            if not account:
                raise ValueError(f"No account found for API key")
            
            # Check if subscription is active
            if not account.subscription_paid:
                raise ValueError(
                    "Subscription payment required. Please update payment method."
                )
            
            # Calculate cost with subscription model
            cost_breakdown = PricingTiers.calculate_cost(
                num_posts=num_posts,
                tier=account.pricing_tier,
                include_comments=include_comments,
                include_media=include_media,
                current_month_posts=account.current_month_posts
            )
            
            # Check spending limit (including potential overage)
            if account.spending_limit:
                projected_total = account.current_month_cost + cost_breakdown["overage"]
                if projected_total > account.spending_limit:
                    raise ValueError(
                        f"Monthly spending limit (${account.spending_limit:.2f}) would be exceeded. "
                        f"Current: ${account.current_month_cost:.2f}, "
                        f"This job: ${cost_breakdown['overage']:.2f}, "
                        f"Projected: ${projected_total:.2f}"
                    )
            
            # Overage only charged, subscription is monthly
            actual_cost = cost_breakdown["overage"]
            is_overage = cost_breakdown["overage_posts"] > 0
            
            # Create usage record
            record = UsageRecord(
                record_id=str(uuid.uuid4()),
                api_key=api_key,
                user_id=account.user_id,
                job_id=job_id,
                timestamp=datetime.now(),
                posts_scraped=num_posts,
                comments_included=include_comments,
                media_included=include_media,
                storage_used_mb=storage_used_mb,
                cost_usd=actual_cost,
                pricing_tier=account.pricing_tier,
                is_overage=is_overage
            )
            
            # Update account
            account.total_posts_scraped += num_posts
            account.total_spent += actual_cost
            account.current_month_posts += num_posts
            account.current_month_cost += actual_cost
            account.current_month_overage_cost += actual_cost
            
            # Deduct from credits if available
            if account.credits_balance > 0 and actual_cost > 0:
                if account.credits_balance >= actual_cost:
                    account.credits_balance -= actual_cost
                    logger.info(f"Deducted ${actual_cost:.4f} from credits. Remaining: ${account.credits_balance:.2f}")
                else:
                    actual_cost -= account.credits_balance
                    account.credits_balance = 0
                    logger.info(f"Credits exhausted. Remaining charge: ${actual_cost:.4f}")
            
            # Save usage record
            self._save_usage_record(record)
            self._save_accounts()
            
            tier_info = PricingTiers.TIERS[account.pricing_tier]
            logger.info(
                f"Recorded usage: {num_posts} posts, ${actual_cost:.4f} overage "
                f"(Month total: {account.current_month_posts}/{tier_info['included_posts']} included, "
                f"${account.current_month_overage_cost:.2f} overage)"
            )
            
            return record
    
    def _save_usage_record(self, record: UsageRecord):
        """Save usage record to monthly file"""
        month_key = record.timestamp.strftime("%Y-%m")
        usage_file = self.usage_dir / f"usage_{month_key}.jsonl"
        
        try:
            with open(usage_file, 'a') as f:
                f.write(json.dumps(record.to_dict()) + '\n')
        except Exception as e:
            logger.error(f"Error saving usage record: {e}")
    
    def get_monthly_usage(self, user_id: str, year: int, month: int) -> Dict[str, Any]:
        """Get usage summary for a specific month"""
        month_key = f"{year:04d}-{month:02d}"
        usage_file = self.usage_dir / f"usage_{month_key}.jsonl"
        
        total_posts = 0
        overage_posts = 0
        total_overage_cost = 0.0
        records = []
        
        if usage_file.exists():
            with open(usage_file, 'r') as f:
                for line in f:
                    if line.strip():
                        record_data = json.loads(line)
                        if record_data['user_id'] == user_id:
                            total_posts += record_data['posts_scraped']
                            total_overage_cost += record_data['cost_usd']
                            if record_data.get('is_overage'):
                                overage_posts += record_data['posts_scraped']
                            records.append(record_data)
        
        account = self.accounts.get(user_id)
        tier_info = PricingTiers.TIERS[account.pricing_tier] if account else None
        
        return {
            "year": year,
            "month": month,
            "total_posts": total_posts,
            "overage_posts": overage_posts,
            "subscription_cost": tier_info["monthly_cost"] if tier_info else 0,
            "overage_cost": total_overage_cost,
            "total_cost": (tier_info["monthly_cost"] if tier_info else 0) + total_overage_cost,
            "num_jobs": len(records),
            "records": records
        }
    
    def get_account_summary(self, api_key: str) -> Dict[str, Any]:
        """Get account summary with subscription details"""
        account = self.get_user_from_api_key(api_key)
        if not account:
            return None
        
        tier_info = PricingTiers.TIERS[account.pricing_tier]
        
        # Check if billing cycle needs reset
        days_since_cycle_start = (datetime.now() - account.billing_cycle_start).days
        if days_since_cycle_start >= 30:
            self._reset_billing_cycle(account)
        
        # Calculate included vs overage
        included_used = min(account.current_month_posts, tier_info["included_posts"])
        overage_posts = max(0, account.current_month_posts - tier_info["included_posts"])
        posts_remaining = max(0, tier_info["included_posts"] - account.current_month_posts)
        
        return {
            "user_id": account.user_id,
            "email": account.email,
            "subscription": {
                "tier": account.pricing_tier,
                "tier_name": tier_info["name"],
                "monthly_cost": tier_info["monthly_cost"],
                "included_posts": tier_info["included_posts"],
                "status": "active" if account.subscription_paid else "payment_required"
            },
            "current_month": {
                "total_posts": account.current_month_posts,
                "included_used": included_used,
                "posts_remaining": posts_remaining,
                "overage_posts": overage_posts,
                "subscription_cost": tier_info["monthly_cost"],
                "overage_cost": account.current_month_overage_cost,
                "total_cost": tier_info["monthly_cost"] + account.current_month_overage_cost,
                "days_remaining": 30 - days_since_cycle_start,
                "billing_cycle_start": account.billing_cycle_start.isoformat()
            },
            "lifetime": {
                "total_posts": account.total_posts_scraped,
                "total_spent": account.total_spent
            },
            "credits_balance": account.credits_balance,
            "spending_limit": account.spending_limit,
            "is_active": account.is_active
        }
    
    def _reset_billing_cycle(self, account: UserAccount):
        """Reset monthly usage counters"""
        with self.lock:
            account.current_month_posts = 0
            account.current_month_cost = 0.0
            account.current_month_overage_cost = 0.0
            account.billing_cycle_start = datetime.now()
            self._save_accounts()
            logger.info(f"Reset billing cycle for user {account.user_id}")
    
    def add_credits(self, user_id: str, amount: float):
        """Add prepaid credits to account"""
        with self.lock:
            if user_id in self.accounts:
                self.accounts[user_id].credits_balance += amount
                self._save_accounts()
                logger.info(f"Added ${amount:.2f} credits to user {user_id}")
    
    def upgrade_tier(self, user_id: str, new_tier: str):
        """Upgrade user to different pricing tier"""
        if new_tier not in PricingTiers.TIERS:
            raise ValueError(f"Invalid tier: {new_tier}")
        
        with self.lock:
            if user_id in self.accounts:
                old_tier = self.accounts[user_id].pricing_tier
                self.accounts[user_id].pricing_tier = new_tier
                self._save_accounts()
                logger.info(f"Upgraded user {user_id} from {old_tier} to {new_tier}")
    
    def generate_invoice(self, user_id: str, year: int, month: int) -> Dict[str, Any]:
        """Generate invoice with subscription + overage model"""
        account = self.accounts.get(user_id)
        if not account:
            return None
        
        usage = self.get_monthly_usage(user_id, year, month)
        tier_info = PricingTiers.TIERS[account.pricing_tier]
        
        invoice = {
            "invoice_id": f"INV-{user_id[:8]}-{year}{month:02d}",
            "user_id": user_id,
            "email": account.email,
            "period": f"{year}-{month:02d}",
            "pricing_tier": account.pricing_tier,
            "line_items": [
                {
                    "description": f"{tier_info['name']} Subscription - {tier_info['included_posts']:,} posts included",
                    "quantity": 1,
                    "unit_price": tier_info["monthly_cost"],
                    "amount": tier_info["monthly_cost"]
                }
            ],
            "usage_summary": {
                "total_posts": usage["total_posts"],
                "included_posts": tier_info["included_posts"],
                "posts_within_limit": min(usage["total_posts"], tier_info["included_posts"]),
                "overage_posts": usage["overage_posts"],
                "num_jobs": usage["num_jobs"]
            },
            "charges": {
                "subscription": tier_info["monthly_cost"],
                "overage": usage["overage_cost"],
                "subtotal": tier_info["monthly_cost"] + usage["overage_cost"],
                "credits_applied": 0,
                "total": usage["total_cost"]
            },
            "generated_at": datetime.now().isoformat()
        }
        
        # Add overage line item if applicable
        if usage["overage_posts"] > 0:
            avg_overage_rate = usage["overage_cost"] / usage["overage_posts"] if usage["overage_posts"] > 0 else 0
            invoice["line_items"].append({
                "description": f"Overage: {usage['overage_posts']:,} additional posts",
                "quantity": usage["overage_posts"],
                "unit_price": avg_overage_rate,
                "amount": usage["overage_cost"]
            })
        
        return invoice