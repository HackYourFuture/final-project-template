-- The grain of int_posting_tags: one row per posting and tag.
--
-- A singular test is any query that should return no rows. This one returns
-- the pairs that appear more than once, so a failure tells you which tag on
-- which posting broke the rule, not just that something did.
select posting_id, tag, count(*) as rows_found
from {{ ref("int_posting_tags") }}
group by posting_id, tag
having count(*) > 1
