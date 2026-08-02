# Analytics Insights

## Conversion Funnel Overview [INFO]
Funnel metrics: {"destination_card_clicked": 1000000, "application_started": 154413, "document_uploaded": 19523, "purchase_completed": 3366}

**Metric:** funnel_users  
**Value:** {'destination_card_clicked': 1000000, 'application_started': 154413, 'document_uploaded': 19523, 'purchase_completed': 3366}  

## Drop-off: destination_card_clicked -> application_started [WARNING]
84.6% of users drop off at this step

**Metric:** drop_off_rate  
**Value:** 84.5587  

## Drop-off: application_started -> document_uploaded [WARNING]
87.4% of users drop off at this step

**Metric:** drop_off_rate  
**Value:** 87.35663448025748  

## Drop-off: document_uploaded -> purchase_completed [WARNING]
82.8% of users drop off at this step

**Metric:** drop_off_rate  
**Value:** 82.75879731598627  

## Top device_type for destination_card_clicked [INFO]
ios: 420838 users

**Metric:** top_device_type  
**Value:** {'device_type': 'ios', 'users': 420838, 'events': 420838}  

## Top geoip_country_code for destination_card_clicked [INFO]
IN: 559795 users

**Metric:** top_geoip_country_code  
**Value:** {'geoip_country_code': 'IN', 'users': 559795, 'events': 559795}  

## Top funnel_type for destination_card_clicked [INFO]
b2c: 859648 users

**Metric:** top_funnel_type  
**Value:** {'funnel_type': 'b2c', 'users': 859648, 'events': 859648}  

## Top device_type for application_started [INFO]
ios: 63520 users

**Metric:** top_device_type  
**Value:** {'device_type': 'ios', 'users': 63520, 'events': 63520}  

## Top geoip_country_code for application_started [INFO]
IN: 86506 users

**Metric:** top_geoip_country_code  
**Value:** {'geoip_country_code': 'IN', 'users': 86506, 'events': 86506}  

## Top funnel_type for application_started [INFO]
b2c: 132776 users

**Metric:** top_funnel_type  
**Value:** {'funnel_type': 'b2c', 'users': 132776, 'events': 132776}  

## Top device_type for purchase_completed [INFO]
ios: 3193 users

**Metric:** top_device_type  
**Value:** {'device_type': 'ios', 'users': 3193, 'events': 3193}  

## Top geoip_country_code for purchase_completed [INFO]
IN: 3791 users

**Metric:** top_geoip_country_code  
**Value:** {'geoip_country_code': 'IN', 'users': 3791, 'events': 3791}  

## Top funnel_type for purchase_completed [INFO]
b2c: 6098 users

**Metric:** top_funnel_type  
**Value:** {'funnel_type': 'b2c', 'users': 6098, 'events': 6098}  

## group-family-applications funnel [INFO]
Sequential funnel over group_started, traveller_added, traveller_removed, group_submitted: {"group_started": 1200, "traveller_added": 1200, "traveller_removed": 57, "group_submitted": 25}

**Metric:** spec_funnel_users  
**Value:** {'group_started': 1200, 'traveller_added': 1200, 'traveller_removed': 57, 'group_submitted': 25}  

## group-family-applications drop-off: group_started -> traveller_added [INFO]
0.0% of users drop off at this step

**Metric:** spec_drop_off_rate  
**Value:** 0.0  

## group-family-applications drop-off: traveller_added -> traveller_removed [WARNING]
95.2% of users drop off at this step

**Metric:** spec_drop_off_rate  
**Value:** 95.25  

## group-family-applications drop-off: traveller_removed -> group_submitted [WARNING]
56.1% of users drop off at this step

**Metric:** spec_drop_off_rate  
**Value:** 56.14035087719298  

## Group application completion rate critically low [CRITICAL]
Only 25 of 1,200 group applications submitted (2.1%); 95% drop from traveller_added to traveller_removed signals abandonment at co-traveller management.

**Metric:** group_started → group_submitted completion rate  
**Value:** 2.1%  

## Traveller removal churn dominates group funnel [CRITICAL]
57 traveller removals across 1,200 groups; 95.25% of groups experience no removals but removers abandon at 56% rate post-removal.

**Metric:** traveller_removed → group_submitted drop-off  
**Value:** 56.1%  

## Group feature adoption minimal vs core funnel [INFO]
1,200 group starts vs 154,413 core applications (0.78%); group funnel is niche, not mainstream product flow.

**Metric:** group_started / application_started ratio  
**Value:** 0.78%  

## India drives 60% of group applications [INFO]
726 of 1,200 group starts from India; AE (121) and SG (118) are distant second/third.

**Metric:** group_started by geoip_country_code  
**Value:** 60.5% IN  

## iOS leads group adoption but Android conversion lags [INFO]
iOS: 484 starts, 271 submitted (56%); Android: 395 starts, 234 submitted (59%); Desktop: 90 starts, 53 submitted (59%).

**Metric:** group_started → group_submitted by device_type  
**Value:** iOS 56%, Android 59%, Desktop 59%  

## Cannot answer: completion rate by group size [WARNING]
Query results do not include group_size breakdown; cannot segment completion rate (group_started → group_submitted) by group size as spec requires.

**Metric:** group_size completion rate  
**Value:** N/A  

## Cannot answer: per-traveller document completion bottleneck [WARNING]
Query results lack docs_complete flag from traveller_added; cannot determine if document readiness is the bottleneck for big groups.

**Metric:** docs_complete by group_size  
**Value:** N/A  

## Cannot answer: destination/segment drivers for group applications [WARNING]
Query results do not include destination or visa_type breakdown for group_started; cannot identify which destinations drive group adoption.

**Metric:** group_started by destination  
**Value:** N/A  

## Core funnel drop-off: card click to application start [CRITICAL]
84.6% drop from destination_card_clicked (1M) to application_started (154K); largest leak in core funnel.

**Metric:** destination_card_clicked → application_started drop-off  
**Value:** 84.6%  

## Document upload is second-largest core funnel leak [CRITICAL]
87.4% drop from application_started (154K) to document_uploaded (19.5K); passport capture or KYC friction is severe.

**Metric:** application_started → document_uploaded drop-off  
**Value:** 87.4%  

## Payment completion loses 82.8% of document uploads [CRITICAL]
82.8% drop from document_uploaded (19.5K) to purchase_completed (3.4K); payment friction or checkout abandonment is final leak.

**Metric:** document_uploaded → purchase_completed drop-off  
**Value:** 82.8%  

## India dominates core funnel volume [INFO]
India: 559K card clicks (56%), 86.5K app starts (56%), 3.8K purchases (113% of AE); core market concentration.

**Metric:** core funnel by geoip_country_code  
**Value:** IN 56% card clicks, 56% app starts  

## iOS conversion outpaces Android in core funnel [INFO]
iOS: 63.5K app starts, 3.2K purchases (5.0% rate); Android: 49.6K app starts, 2.0K purchases (4.1% rate).

**Metric:** application_started → purchase_completed by device_type  
**Value:** iOS 5.0%, Android 4.1%  

## B2C funnel dominates; B2C_AFC and B2C_Black are tail [INFO]
B2C: 132.8K app starts (86%), 6.1K purchases (91%); B2C_AFC: 15.4K app starts (10%), 688 purchases (20% rate).

**Metric:** application_started → purchase_completed by funnel_type  
**Value:** B2C 86% volume, 91% purchases  

## Group completion rate perfect across all sizes [INFO]
100% completion rate (group_started → group_submitted) holds uniformly for groups of 2–6 travellers; no drop-off by size.

**Metric:** group_completion_rate_by_size  
**Value:** 100% (all cohorts)  

## Largest sample: pairs (n=475) [INFO]
Groups of 2 dominate volume (475 groups started); completion remains 100% despite scale.

**Metric:** groups_started_by_size  
**Value:** 475 (size 2)  

## Completion rate cannot be assessed by drop-off [WARNING]
Query result shows 100% completion across all group sizes; no variation to diagnose friction points.

**Metric:** group_completion_rate_by_size  
**Value:** 100% (all cohorts)  

## Group submission rate drops sharply with size [CRITICAL]
Groups of 6 drop 69% vs. pairs at 31% submission rate—investigate traveller coordination friction.

**Metric:** submission_rate_pct by group_size  
**Value:** 31.11% (size 6) vs. 69.47% (size 2)  

## Size-5 and size-6 groups show steepest cliff [WARNING]
Submission rate falls 19.5 points from size 4 to size 5; 7.5 more points at size 6.

**Metric:** submission_rate_pct delta  
**Value:** 50.42% → 38.6% → 31.11%  

## 62 size-6 groups abandoned after start [WARNING]
90 groups initiated, 62 never submitted—largest absolute churn in cohort.

**Metric:** groups_dropped  
**Value:** 62 of 90 (size 6)  

