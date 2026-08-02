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

## promo-coupon-checkout funnel [INFO]
Sequential funnel over coupon_field_shown, coupon_entered, coupon_applied, coupon_rejected, discount_shown, checkout_with_coupon: {"coupon_field_shown": 2100, "coupon_entered": 777, "coupon_applied": 408, "coupon_rejected": 0, "discount_shown": 0, "checkout_with_coupon": 0}

**Metric:** spec_funnel_users  
**Value:** {'coupon_field_shown': 2100, 'coupon_entered': 777, 'coupon_applied': 408, 'coupon_rejected': 0, 'discount_shown': 0, 'checkout_with_coupon': 0}  

## promo-coupon-checkout drop-off: coupon_field_shown -> coupon_entered [WARNING]
63.0% of users drop off at this step

**Metric:** spec_drop_off_rate  
**Value:** 63.0  

## promo-coupon-checkout drop-off: coupon_entered -> coupon_applied [INFO]
47.5% of users drop off at this step

**Metric:** spec_drop_off_rate  
**Value:** 47.49034749034749  

## promo-coupon-checkout drop-off: coupon_applied -> coupon_rejected [WARNING]
100.0% of users drop off at this step

**Metric:** spec_drop_off_rate  
**Value:** 100.0  

## Coupon field shown but 63% abandon before entry [WARNING]
2,100 users see coupon field; only 777 enter a code. Investigate friction in coupon input UX.

**Metric:** coupon_field_shown → coupon_entered drop-off  
**Value:** 63.0%  

## Half of entered coupons fail validation [WARNING]
777 codes entered, 408 applied, 369 rejected. Identify top reject reasons to guide code quality.

**Metric:** coupon_entered → coupon_applied success rate  
**Value:** 52.5%  

## No coupon rejections logged despite 369 failures [CRITICAL]
coupon_rejected table shows 0 rows but 369 users failed validation. Check instrumentation gap.

**Metric:** coupon_rejected event coverage  
**Value:** 0 rows  

## Discount shown but checkout_with_coupon never fires [CRITICAL]
408 discounts shown; 0 checkout_with_coupon events. Verify event firing logic post-discount display.

**Metric:** discount_shown → checkout_with_coupon  
**Value:** 0%  

## India dominates coupon engagement but low conversion [INFO]
1,275 of 2,100 field-shown (61%) are India; only 361 of 777 entered (47%) convert to applied.

**Metric:** coupon_applied rate by geo (IN)  
**Value:** 28.3% (IN) vs 25.8% (overall)  

## iOS leads coupon adoption but Android rejects more [INFO]
iOS: 254 applied / 364 entered (70%). Android: 174 applied / 264 entered (66%). Validate Android code quality.

**Metric:** coupon_entered → coupon_applied by device  
**Value:** iOS 70% vs Android 66%  

## Cannot measure coupon conversion lift vs baseline [CRITICAL]
checkout_with_coupon table has 0 rows; cannot compare coupon users to no-coupon baseline conversion.

**Metric:** conversion_lift (coupon vs no-coupon)  
**Value:** unmeasurable  

## Cannot compute total margin cost from coupons [CRITICAL]
coupon_applied and discount_shown tables lack discount_amount values in query results. Cannot sum margin impact.

**Metric:** total discount_amount  
**Value:** not provided  

