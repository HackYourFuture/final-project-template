-- A posting dated in the future means the source changed its date format or
-- your parsing is wrong. Either way you want to know before the backend does.
select posting_id, posted_at
from {{ ref("fct_postings") }}
where posted_at > current_timestamp() + interval 1 day
