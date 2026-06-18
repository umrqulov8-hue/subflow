-- Run this in Supabase Dashboard → SQL Editor

-- Payments table
CREATE TABLE IF NOT EXISTS payments (
  id BIGSERIAL PRIMARY KEY,
  order_id TEXT UNIQUE NOT NULL,
  user_id UUID REFERENCES auth.users(id),
  email TEXT,
  amount NUMERIC(10,2) NOT NULL,
  currency TEXT DEFAULT 'USD',
  plan_name TEXT DEFAULT 'pro',
  status TEXT DEFAULT 'pending',
  cheque_id TEXT,
  card_last4 TEXT,
  card_masked TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Subscriptions table
CREATE TABLE IF NOT EXISTS subscriptions (
  id BIGSERIAL PRIMARY KEY,
  user_id UUID UNIQUE REFERENCES auth.users(id),
  plan_name TEXT DEFAULT 'pro',
  status TEXT DEFAULT 'none',
  expires_at TIMESTAMPTZ,
  auto_renew BOOLEAN DEFAULT true,
  payment_id TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Enable RLS
ALTER TABLE payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;

-- Policies: users can only see their own data
CREATE POLICY "users_view_own_payments" ON payments
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "users_view_own_subscriptions" ON subscriptions
  FOR SELECT USING (auth.uid() = user_id);

-- Service role can do everything (for webhook)
CREATE POLICY "service_role_all_payments" ON payments
  FOR ALL USING (true);

CREATE POLICY "service_role_all_subscriptions" ON subscriptions
  FOR ALL USING (true);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_payments_order_id ON payments(order_id);
CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payments(user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id);
