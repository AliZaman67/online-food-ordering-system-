"""Generates seed.sql: fictional, internally consistent demo data.
Run:  python make_seed.py      (then delete food_ordering.db to rebuild)
Logins:  admin@crave.test / admin1234   |   ayesha@mail.test (and 9 others) / demo1234
"""
import hashlib, os, random
random.seed(7)

def hash_pw(pw, iters=120_000):
    salt = os.urandom(8).hex()
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), iters).hex()
    return f"pbkdf2${iters}${salt}${h}"

def s(x): return "'" + str(x).replace("'", "''") + "'"
o = []

CATS = ["Mains", "Sides", "Drinks", "Desserts"]
for i, c in enumerate(CATS, 1): o.append(f"INSERT INTO Categories VALUES({i},{s(c)});")

o.append(f"INSERT INTO Users(user_id,name,email,phone,address,password_hash,role) VALUES(1,'Crave Admin','admin@crave.test','021-3500000','HQ, Karachi',{s(hash_pw('admin1234'))},'admin');")
C = ["Ayesha Khan","Bilal Ahmed","Sara Malik","Hamza Ali","Fatima Noor","Usman Tariq","Zainab Raza","Omar Farooq","Hina Siddiqui","Daniyal Shah"]
demo = hash_pw("demo1234")
for i, n in enumerate(C, 2):
    o.append(f"INSERT INTO Users(user_id,name,email,phone,address,password_hash) VALUES({i},{s(n)},{s(n.split()[0].lower()+'@mail.test')},'0300-55500{i:02d}',{s('House '+str(i*7)+', Block '+str(i)+', Karachi')},{s(demo)});")

# name, cuisine, area, emoji, fee, min, eta
R = [("Burger Barn","American","Clifton","🍔",150,500,25),
     ("Pizza Palace","Italian","DHA Phase 5","🍕",200,800,35),
     ("Spice Route","Pakistani","Gulshan-e-Iqbal","🍛",120,600,40),
     ("Sushi Zen","Japanese","Bahadurabad","🍣",250,1000,45)]
for i, (n,cu,a,e,f,m,eta) in enumerate(R, 1):
    o.append(f"INSERT INTO Restaurants VALUES({i},{s(n)},{s(cu)},{s(a)},'021-3500{i}00',{s(e)},{f},{m},{eta},1);")

# restaurant -> (name, category_id, emoji, price, veg, description)
M = [[("Classic Burger",1,"🍔",650,0,"Smashed beef patty, pickles, house sauce"),("Cheese Burger",1,"🧀",750,0,"Double cheddar, caramelised onions"),
      ("Crinkle Fries",2,"🍟",300,1,"Crisp, salted, extra crunchy"),("Chicken Wings",2,"🍗",550,0,"Six wings, smoky buffalo glaze"),
      ("Oreo Shake",3,"🥤",400,1,"Thick vanilla shake with cookie crumb"),("Brownie Sundae",4,"🍨",480,1,"Warm brownie, vanilla scoop, fudge")],
     [("Margherita",1,"🍕",1100,1,"San Marzano tomato, mozzarella, basil"),("Pepperoni",1,"🍕",1400,0,"Spicy pepperoni, double cheese"),
      ("Garlic Bread",2,"🥖",450,1,"Toasted with herb butter"),("Pasta Alfredo",1,"🍝",950,0,"Creamy parmesan sauce, grilled chicken"),
      ("Cola",3,"🥤",150,1,"Chilled 345 ml can"),("Tiramisu",4,"🍰",620,1,"Espresso-soaked sponge, mascarpone")],
     [("Chicken Biryani",1,"🍛",500,0,"Slow-cooked basmati, tender chicken"),("Beef Karahi",1,"🥘",1600,0,"Wok-fired beef, tomato, green chilli"),
      ("Butter Naan",2,"🫓",60,1,"Tandoor-baked, brushed with butter"),("Seekh Kabab",2,"🍢",700,0,"Charcoal-grilled spiced mince"),
      ("Mango Lassi",3,"🥭",250,1,"Sweet yoghurt and Sindhri mango"),("Gulab Jamun",4,"🍮",300,1,"Four warm syrup-soaked dumplings")],
     [("Salmon Roll",1,"🍣",1300,0,"Eight pieces, avocado centre"),("Veg Maki",1,"🥒",800,1,"Cucumber, carrot, sesame"),
      ("Miso Soup",2,"🍲",400,1,"Tofu, wakame, spring onion"),("Ramen",1,"🍜",1200,0,"Pork broth, soft egg, nori"),
      ("Green Tea",3,"🍵",200,1,"Hot sencha, unsweetened"),("Mochi Trio",4,"🍡",650,1,"Matcha, strawberry, sesame")]]
items = {}; iid = 0
for r, ms in enumerate(M, 1):
    for n,c,e,p,v,d in ms:
        iid += 1; items[iid] = (r, p)
        o.append(f"INSERT INTO Menu_Items VALUES({iid},{r},{c},{s(n)},{s(d)},{s(e)},{p},{v},1);")

for i,(n,st) in enumerate([("Imran","Available"),("Kashif","Available"),("Nadia","Available"),("Raza","Offline")], 1):
    o.append(f"INSERT INTO Delivery_Riders VALUES({i},{s(n)},'0311-77700{i:02d}',{s(st)});")
o.append("INSERT INTO Coupons VALUES('WELCOME10',10,500,'2027-12-31',1);")
o.append("INSERT INTO Coupons VALUES('FEAST20',20,2000,'2027-12-31',1);")
o.append("INSERT INTO Coupons VALUES('OLD5',5,0,'2026-01-01',1);")   # expired: demonstrates validation

FLOW = ['Pending','Confirmed','Preparing','Out for Delivery','Delivered']
oi = pid = rv = 0
COMMENTS = ["Arrived hot and fast.","Great portions, will order again.","Tasty, but delivery was a little slow.","Perfect as always.","Loved it."]
for oid in range(1, 29):
    u = random.randint(2, 11); r = random.randint(1, 4)
    final = random.choice(['Delivered']*12+['Cancelled']*3+['Pending']*4+['Confirmed']*3+['Preparing']*3+['Out for Delivery']*3)
    pick = random.sample([k for k,v in items.items() if v[0]==r], random.randint(1,4))
    sub = 0; lines = []
    for k in pick:
        q = random.randint(1,3); sub += q*items[k][1]; oi += 1
        lines.append(f"INSERT INTO Order_Items VALUES({oi},{oid},{k},{q},{items[k][1]});")
    fee = R[r-1][4]; coupon = 'WELCOME10' if sub >= 500 and random.random() < .3 else None
    disc = round(sub*.10) if coupon else 0; tot = sub - disc + fee
    d = f"2026-10-{random.randint(1,19):02d} {random.randint(11,22)}:{random.randint(0,59):02d}:00"
    o.append(f"INSERT INTO Orders(order_id,user_id,restaurant_id,coupon_code,order_date,subtotal,discount,delivery_fee,total_amount,delivery_address) "
             f"VALUES({oid},{u},{r},{s(coupon) if coupon else 'NULL'},{s(d)},{sub},{disc},{fee},{tot},{s('Block '+str(u)+', Karachi')});")
    o += lines
    rider = random.randint(1,3)
    path = FLOW[:FLOW.index(final)+1] if final != 'Cancelled' else random.choice([['Confirmed'],[]]) + ['Cancelled']
    for st in path[1:] if path and path[0]=='Pending' else path:
        if st == 'Out for Delivery': o.append(f"UPDATE Orders SET rider_id={rider} WHERE order_id={oid};")
        o.append(f"UPDATE Orders SET status={s(st)} WHERE order_id={oid};")
    pid += 1; m = random.choice(['Cash','Card','Wallet'])
    ps = 'Paid' if final == 'Delivered' else 'Failed' if final == 'Cancelled' else ('Pending' if m == 'Cash' else 'Paid')
    o.append(f"INSERT INTO Payments VALUES({pid},{oid},{tot},{s(m)},{s(ps)},{s(d)});")
    if final == 'Delivered' and random.random() < .7:
        rv += 1; o.append(f"INSERT INTO Reviews VALUES({rv},{oid},{u},{r},{random.choice([3,4,4,5,5])},{s(random.choice(COMMENTS))},{s(d)});")
o.append("UPDATE Delivery_Riders SET availability_status='Busy' WHERE rider_id IN (SELECT rider_id FROM Orders WHERE status='Out for Delivery');")
o.append("UPDATE Delivery_Riders SET availability_status='Offline' WHERE rider_id=4;")

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "seed.sql"), "w", encoding="utf-8") as f:
    f.write("\n".join(o) + "\n")
print("seed.sql written:", len(o), "statements")
