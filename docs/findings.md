Some emails have HTML data under the mime type text/plain.
Forwarded Emails aren't being parsed correctly (need to find out how to identify these)



## TODO: 
1) SQL Query for emails by normalized text LENGTH by buckets of size 100 (incrementally)
2) Run Parser on sample of emails (take distribution of 200 emails over the buckets uniformly)
3) Evaluate parser performance & run normaliser on emails to evaluate performance.

TODO: Ensure normaliser uses regional block score instead of individual, due to block identification not being robust.
TODO: Store emails that are dropped with appropriate reason (perhaps not occupies to much storage)