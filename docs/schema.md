# Schema

<!-- Written by schema_dump. Do not edit it here. -->

## 001 register

Digest `3646bbdc9c563663`.

### `licence`

| column | type | and |
| --- | --- | --- |
| `serial` | INTEGER | PRIMARY KEY |
| `trading_name` | TEXT | NOT NULL |
| `operator_name` | TEXT | NOT NULL |
| `locality` | TEXT | NOT NULL |
| `period_start` | TEXT | NOT NULL |
| `period_end` | TEXT | NOT NULL |
| `closed_months` | TEXT | NOT NULL |
| `status` | TEXT | NOT NULL |

### `licence_particular`

| column | type | and |
| --- | --- | --- |
| `serial` | INTEGER | NOT NULL REFERENCES licence(serial) ON DELETE CASCADE |
| `claim_key` | TEXT | NOT NULL |
| `kind` | TEXT | NOT NULL |
| `value` | INTEGER | NOT NULL |

### `channel`

| column | type | and |
| --- | --- | --- |
| `slug` | TEXT | PRIMARY KEY |
| `name` | TEXT | NOT NULL |
| `base_url` | TEXT | NOT NULL |
| `syndication` | TEXT | NOT NULL |
| `locale` | TEXT | NOT NULL |
| `scale_slug` | TEXT | NOT NULL |
| `user_agent` | TEXT | NOT NULL |
| `crawl_delay_ms` | INTEGER | NOT NULL |
| `daily_request_ceiling` | INTEGER | NOT NULL |
| `window_open` | INTEGER | NOT NULL |
| `window_close` | INTEGER | NOT NULL |
| `max_pages` | INTEGER | NOT NULL |

### indexes

| index | on | columns | unique |
| --- | --- | --- | --- |
| `licence_locality` | `licence` | locality | no |
| `licence_status` | `licence` | status | no |
| `licence_particular_claim` | `licence_particular` | claim_key | no |

## 002 evidence

Digest `632522ea21676b52`.

### `capture`

| column | type | and |
| --- | --- | --- |
| `digest` | TEXT | PRIMARY KEY |
| `channel` | TEXT | NOT NULL REFERENCES channel(slug) |
| `url` | TEXT | NOT NULL |
| `final_url` | TEXT | NOT NULL |
| `status` | INTEGER | NOT NULL |
| `fetched_at` | TEXT | NOT NULL |
| `byte_count` | INTEGER | NOT NULL |
| `elapsed_ms` | INTEGER | NOT NULL |
| `profile_key` | TEXT | NOT NULL |
| `licence_serial` | INTEGER |   |
| `etag` | TEXT | NOT NULL DEFAULT '' |

### `review`

| column | type | and |
| --- | --- | --- |
| `review_key` | TEXT | PRIMARY KEY |
| `channel` | TEXT | NOT NULL REFERENCES channel(slug) |
| `channel_review_id` | TEXT | NOT NULL |
| `licence_serial` | INTEGER | NOT NULL REFERENCES licence(serial) ON DELETE CASCADE |
| `stay_year` | INTEGER | NOT NULL |
| `stay_month` | INTEGER | NOT NULL |
| `unit_points` | INTEGER | NOT NULL |
| `raw_score` | TEXT | NOT NULL |
| `title` | TEXT | NOT NULL |
| `body` | TEXT | NOT NULL |
| `reviewer_initials` | TEXT | NOT NULL |
| `room_class` | TEXT | NOT NULL |
| `language` | TEXT | NOT NULL |
| `submitted` | TEXT | NOT NULL |
| `operator_response` | TEXT | NOT NULL |
| `capture_digest` | TEXT | NOT NULL REFERENCES capture(digest) |
| `profile_key` | TEXT | NOT NULL |
| `first_seen` | TEXT | NOT NULL |

### indexes

| index | on | columns | unique |
| --- | --- | --- | --- |
| `capture_channel` | `capture` | channel, fetched_at | no |
| `capture_licence` | `capture` | licence_serial | no |
| `review_licence` | `review` | licence_serial, stay_year, stay_month | no |
| `review_channel` | `review` | channel | no |
| `review_capture` | `review` | capture_digest | no |

## 003 listings

Digest `a9e4e1bb2a781ae4`.

### `listing`

| column | type | and |
| --- | --- | --- |
| `licence_serial` | INTEGER | NOT NULL REFERENCES licence(serial) ON DELETE CASCADE |
| `channel` | TEXT | NOT NULL REFERENCES channel(slug) |
| `path` | TEXT | NOT NULL |
| `property_ref` | TEXT | NOT NULL |
| `confirmed_on` | TEXT | NOT NULL |
| `active` | INTEGER | NOT NULL |
| `note` | TEXT | NOT NULL DEFAULT '' |

### indexes

| index | on | columns | unique |
| --- | --- | --- | --- |
| `listing_channel` | `listing` | channel, active | no |
| `listing_property` | `listing` | channel, property_ref | yes |

## 004 remediation

Digest `4498940b8a98f4c2`.

### `remediation`

| column | type | and |
| --- | --- | --- |
| `licence_serial` | INTEGER | NOT NULL REFERENCES licence(serial) ON DELETE CASCADE |
| `claim_key` | TEXT | NOT NULL |
| `reference` | TEXT | NOT NULL |
| `filed_on` | TEXT | NOT NULL |
| `effective_year` | INTEGER | NOT NULL |
| `effective_month` | INTEGER | NOT NULL |
| `accepted` | INTEGER | NOT NULL |
| `note` | TEXT | NOT NULL DEFAULT '' |

### indexes

| index | on | columns | unique |
| --- | --- | --- | --- |
| `remediation_licence` | `remediation` | licence_serial, accepted | no |

## 005 bodies

Digest `52018552012a6f60`.

### `capture_body`

| column | type | and |
| --- | --- | --- |
| `digest` | TEXT | PRIMARY KEY REFERENCES capture(digest) ON DELETE CASCADE |
| `body` | BLOB | NOT NULL |
| `stored_at` | TEXT | NOT NULL |

### indexes

| index | on | columns | unique |
| --- | --- | --- | --- |
| `capture_body_stored` | `capture_body` | stored_at | no |

## 006 operator

Digest `269776a0e609a8bc`.

### `operator`

| column | type | and |
| --- | --- | --- |
| `ref` | TEXT | PRIMARY KEY |
| `name` | TEXT | NOT NULL |
| `contact_name` | TEXT | NOT NULL |
| `email` | TEXT | NOT NULL |
| `address` | TEXT | NOT NULL |
| `registered_on` | TEXT | NOT NULL |
| `note` | TEXT | NOT NULL DEFAULT '' |

### indexes

| index | on | columns | unique |
| --- | --- | --- | --- |
| `licence_operator` | `licence` | operator_ref | no |
| `operator_name` | `operator` | name | no |
