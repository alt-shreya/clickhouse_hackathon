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

## express-checkout funnel [INFO]
Sequential funnel over express_checkout_shown, express_checkout_selected, saved_method_used, otp_entered, express_payment_confirmed: {"express_checkout_shown": 1650, "express_checkout_selected": 1007, "saved_method_used": 1007, "otp_entered": 1007, "express_payment_confirmed": 836}

**Metric:** spec_funnel_users  
**Value:** {'express_checkout_shown': 1650, 'express_checkout_selected': 1007, 'saved_method_used': 1007, 'otp_entered': 1007, 'express_payment_confirmed': 836}  

## express-checkout drop-off: express_checkout_shown -> express_checkout_selected [INFO]
39.0% of users drop off at this step

**Metric:** spec_drop_off_rate  
**Value:** 38.96969696969697  

## express-checkout drop-off: express_checkout_selected -> saved_method_used [INFO]
0.0% of users drop off at this step

**Metric:** spec_drop_off_rate  
**Value:** 0.0  

## express-checkout drop-off: saved_method_used -> otp_entered [INFO]
0.0% of users drop off at this step

**Metric:** spec_drop_off_rate  
**Value:** 0.0  

## express-checkout drop-off: otp_entered -> express_payment_confirmed [INFO]
17.0% of users drop off at this step

**Metric:** spec_drop_off_rate  
**Value:** 16.9811320754717  

## Express checkout adoption strong but show-to-select gap [WARNING]
39% of users shown Express checkout drop off before selecting it; 1,650 shown, 1,007 selected.

**Metric:** express_checkout_shown → express_checkout_selected drop-off  
**Value:** 38.97%  

## Express payment OTP-to-confirm drop-off at 17% [WARNING]
170 of 1,007 users fail to confirm after entering OTP; 17% abandonment at final step.

**Metric:** otp_entered → express_payment_confirmed drop-off  
**Value:** 16.98%  

## Express checkout conversion: 836 of 1,650 shown (50.6%) [INFO]
Express payment confirmed for 50.6% of users shown Express; baseline core funnel is 2.2% (3,366 / 154,413 app starters).

**Metric:** express_payment_confirmed / express_checkout_shown  
**Value:** 50.6%  

## iOS Express adoption leads Android by 4 points [INFO]
iOS: 316/702 shown = 45% confirmed. Android: 303/538 shown = 56% confirmed. Android outperforms iOS.

**Metric:** express_payment_confirmed by device_type  
**Value:** iOS 45%, Android 56%  

## India dominates Express volume but lower conversion [INFO]
509 of 1,007 Express users (50.5%) are India; 509/1,007 confirmed = 50.5% vs SG 71/147 = 48.3%.

**Metric:** express_payment_confirmed by geoip_country_code  
**Value:** IN: 509/1,007 (50.5%)  

## No OTP success/failure split in query results [WARNING]
Cannot answer whether OTP fails more on iOS vs Android; otp_entered shows 1,007 events but no failure column.

**Metric:** otp_success by platform  
**Value:** N/A  

## No payment latency data in query results [WARNING]
Cannot measure Express speed vs standard checkout; payment.latency_ms not present in spec_analysis.

**Metric:** payment.latency_ms (Express vs Standard)  
**Value:** N/A  

## No standard checkout baseline for comparison [CRITICAL]
Cannot compute Express lift vs standard checkout; standard checkout funnel not in query results.

**Metric:** Express vs Standard checkout conversion lift  
**Value:** N/A  

## Saved method adoption 100% among Express users [INFO]
All 1,007 users who selected Express used a saved payment method; no drop-off between selection and saved_method_used.

**Metric:** saved_method_used / express_checkout_selected  
**Value:** 100%  

## Web-user-b2c Express adoption lags mobile [INFO]
Web: 170/318 shown = 53% confirmed. iOS: 316/702 = 45%. Desktop: 47/92 = 51%.

**Metric:** express_payment_confirmed by device_type (web-user-b2c)  
**Value:** 53%  

