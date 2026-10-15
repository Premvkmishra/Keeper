CREATE UNIQUE INDEX IF NOT EXISTS uq_household_member_user_id_idx
    ON household_members(user_id);
