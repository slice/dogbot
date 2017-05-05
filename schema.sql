CREATE TABLE IF NOT EXISTS command_statistics (
  command_name text,
  times_used int,
  last_used timestamp
);

CREATE TABLE IF NOT EXISTS rps_exclusions (
  user_id bigint
);
