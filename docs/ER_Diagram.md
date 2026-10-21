# ER Diagram (renders on GitHub, VS Code, or mermaid.live)
```mermaid
erDiagram
  Users ||--o{ Orders : places
  Users ||--o{ Reviews : writes
  Restaurants ||--o{ Orders : receives
  Restaurants ||--o{ Menu_Items : offers
  Restaurants ||--o{ Reviews : "rated by"
  Categories ||--o{ Menu_Items : groups
  Delivery_Riders |o--o{ Orders : delivers
  Coupons |o--o{ Orders : "discounts"
  Orders ||--|{ Order_Items : contains
  Orders ||--|| Payments : "paid by"
  Orders ||--|{ Order_Status_History : tracks
  Orders ||--o| Reviews : "reviewed in"
  Menu_Items ||--o{ Order_Items : "appears in"
  Users { int user_id PK string email UK string password_hash string role }
  Restaurants { int restaurant_id PK string name string cuisine numeric delivery_fee numeric min_order int is_open }
  Categories { int category_id PK string name UK }
  Menu_Items { int item_id PK int restaurant_id FK int category_id FK numeric price int is_veg int is_available }
  Delivery_Riders { int rider_id PK string name string availability_status }
  Coupons { string code PK int discount_percent numeric min_order string expires_on }
  Orders { int order_id PK int user_id FK int restaurant_id FK int rider_id FK string coupon_code FK string status numeric subtotal numeric discount numeric delivery_fee numeric total_amount }
  Order_Items { int order_item_id PK int order_id FK int item_id FK int quantity numeric unit_price }
  Payments { int payment_id PK int order_id FK,UK string method string status }
  Order_Status_History { int history_id PK int order_id FK string status string changed_at }
  Reviews { int review_id PK int order_id FK,UK int user_id FK int restaurant_id FK int rating }
```

## Design notes
- **3NF**: every non-key column depends only on its table's key. `Order_Items.unit_price` is deliberately copied from `Menu_Items.price` so past orders keep the price they were bought at.
- **Triggers** write `Order_Status_History` and flip rider availability, so the rules hold no matter which client touches the database.
- **Constraints**: CHECKs on every status/enum/price/rating, FOREIGN KEYs everywhere (enabled per connection), UNIQUE email, one payment and one review per order.
