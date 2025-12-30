#!/usr/bin/env python3
"""
Setup Accounts Script
Initialize user accounts with API keys from your key manager
"""

import sys
from pathlib import Path
from usage_tracker import UsageTracker

def setup_accounts():
    """
    Setup initial user accounts
    """
    # Initialize usage tracker
    data_dir = Path("./data")
    usage_tracker = UsageTracker(data_dir)
    
    print("=" * 60)
    print("Instagram Scraper API - Account Setup")
    print("=" * 60)
    print()
    
    # Get user information
    print("Let's create your first user account!")
    print()
    
    email = input("Enter user email: ").strip()
    if not email or '@' not in email:
        print("❌ Invalid email address")
        return
    
    print()
    print("Enter API keys (comma-separated, from your key_manager.html):")
    print("Example: sk_abc123,sk_def456")
    api_keys_input = input("API Keys: ").strip()
    
    if not api_keys_input:
        print("❌ At least one API key is required")
        return
    
    api_keys = [key.strip() for key in api_keys_input.split(',') if key.strip()]
    
    if not api_keys:
        print("❌ No valid API keys provided")
        return
    
    print()
    print("Select pricing tier:")
    print("1. Starter ($0.01/post) - 1,000 posts/month included")
    print("2. Professional ($0.0075/post) - 5,000 posts/month included [RECOMMENDED]")
    print("3. Enterprise ($0.005/post) - 20,000 posts/month included")
    
    tier_choice = input("Choice (1-3) [2]: ").strip() or "2"
    
    tier_map = {
        "1": "starter",
        "2": "professional",
        "3": "enterprise"
    }
    
    pricing_tier = tier_map.get(tier_choice, "professional")
    
    print()
    spending_limit_input = input("Monthly spending limit (USD) [optional, press Enter to skip]: ").strip()
    spending_limit = None
    
    if spending_limit_input:
        try:
            spending_limit = float(spending_limit_input)
            if spending_limit <= 0:
                print("⚠️  Spending limit must be positive. Skipping limit.")
                spending_limit = None
        except ValueError:
            print("⚠️  Invalid amount. Skipping spending limit.")
            spending_limit = None
    
    # Create account
    print()
    print("Creating account...")
    
    try:
        account = usage_tracker.create_account(
            email=email,
            api_keys=api_keys,
            pricing_tier=pricing_tier,
            spending_limit=spending_limit
        )
        
        print()
        print("✅ Account created successfully!")
        print()
        print("=" * 60)
        print("ACCOUNT DETAILS")
        print("=" * 60)
        print(f"User ID:       {account.user_id}")
        print(f"Email:         {account.email}")
        print(f"Pricing Tier:  {account.pricing_tier.upper()}")
        print(f"Base Rate:     ${account.pricing_tier and UsageTracker.pricing_tiers.TIERS[account.pricing_tier]['base_price']}/post")
        print(f"API Keys:      {len(account.api_keys)} key(s)")
        
        for i, key in enumerate(account.api_keys, 1):
            print(f"  Key {i}: {key[:20]}...")
        
        if spending_limit:
            print(f"Spending Limit: ${spending_limit:.2f}/month")
        else:
            print(f"Spending Limit: None (unlimited)")
        
        print()
        print("=" * 60)
        print("NEXT STEPS")
        print("=" * 60)
        print("1. Update your .env file with these API keys")
        print("2. Restart your API server")
        print("3. Test with api_tester.html using one of the keys above")
        print("4. Check usage at: GET /usage/summary")
        print()
        print("Example .env entry:")
        print(f"API_KEYS={','.join(account.api_keys)}")
        print()
        
    except Exception as e:
        print(f"❌ Error creating account: {str(e)}")
        return


def list_accounts():
    """
    List all existing accounts
    """
    data_dir = Path("./data")
    usage_tracker = UsageTracker(data_dir)
    
    if not usage_tracker.accounts:
        print("No accounts found.")
        return
    
    print()
    print("=" * 60)
    print("EXISTING ACCOUNTS")
    print("=" * 60)
    print()
    
    for user_id, account in usage_tracker.accounts.items():
        print(f"User ID:     {user_id}")
        print(f"Email:       {account.email}")
        print(f"Tier:        {account.pricing_tier}")
        print(f"API Keys:    {len(account.api_keys)}")
        print(f"Total Posts: {account.total_posts_scraped}")
        print(f"Total Spent: ${account.total_spent:.2f}")
        print(f"This Month:  {account.current_month_posts} posts, ${account.current_month_cost:.2f}")
        print(f"Credits:     ${account.credits_balance:.2f}")
        print(f"Active:      {account.is_active}")
        print("-" * 60)
        print()


def add_credits():
    """
    Add credits to an account
    """
    data_dir = Path("./data")
    usage_tracker = UsageTracker(data_dir)
    
    if not usage_tracker.accounts:
        print("No accounts found. Create an account first.")
        return
    
    # List accounts
    print()
    print("Available accounts:")
    for i, (user_id, account) in enumerate(usage_tracker.accounts.items(), 1):
        print(f"{i}. {account.email} ({user_id[:8]}...) - Balance: ${account.credits_balance:.2f}")
    
    print()
    choice = input("Select account number: ").strip()
    
    try:
        idx = int(choice) - 1
        user_id = list(usage_tracker.accounts.keys())[idx]
        account = usage_tracker.accounts[user_id]
    except (ValueError, IndexError):
        print("❌ Invalid selection")
        return
    
    amount_input = input(f"Amount to add (USD) for {account.email}: ").strip()
    
    try:
        amount = float(amount_input)
        if amount <= 0:
            print("❌ Amount must be positive")
            return
    except ValueError:
        print("❌ Invalid amount")
        return
    
    usage_tracker.add_credits(user_id, amount)
    
    print()
    print(f"✅ Added ${amount:.2f} credits to {account.email}")
    print(f"New balance: ${account.credits_balance + amount:.2f}")


def main():
    """
    Main menu
    """
    while True:
        print()
        print("=" * 60)
        print("Instagram Scraper API - Account Manager")
        print("=" * 60)
        print()
        print("1. Create new account")
        print("2. List all accounts")
        print("3. Add credits to account")
        print("4. Exit")
        print()
        
        choice = input("Select option (1-4): ").strip()
        
        if choice == "1":
            setup_accounts()
        elif choice == "2":
            list_accounts()
        elif choice == "3":
            add_credits()
        elif choice == "4":
            print("Goodbye!")
            break
        else:
            print("Invalid option. Please try again.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nExiting...")
        sys.exit(0)