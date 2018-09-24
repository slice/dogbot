CREATE TABLE activitypub_actor_links (
  user_id BIGINT,
  actor_link TEXT,
  profile_page_link TEXT,
  username TEXT,

  PRIMARY KEY(user_id)
);
