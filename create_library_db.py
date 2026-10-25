import sqlite3
from pathlib import Path

db_path = Path(__file__).with_name("library.db")
connection = sqlite3.connect(db_path)
cursor = connection.cursor()

cursor.execute("DROP TABLE IF EXISTS books")
cursor.execute("""
CREATE TABLE books (
    book_id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    category TEXT NOT NULL,
    available_copies INTEGER NOT NULL CHECK (available_copies >= 0),
    times_borrowed INTEGER NOT NULL CHECK (times_borrowed >= 0)
)
""")

# (title, author, category, available_copies, times_borrowed)
books = [
    # Science
    ("The Wonders of Physics", "Dr. Amir Hashmi", "Science", 4, 42),
    ("Chemistry Made Easy", "Sana Rehman", "Science", 0, 55),
    ("Life Inside a Cell", "Dr. Nadia Karim", "Science", 3, 28),
    ("Our Solar System", "Faisal Qureshi", "Science", 5, 31),
    ("Human Body Explained", "Dr. Hina Baig", "Science", 2, 47),
    ("Earth and Weather", "Omar Siddiqui", "Science", 0, 36),
    ("Simple Machines", "Bilal Anwar", "Science", 6, 19),
    ("Plants Around Us", "Mariam Zafar", "Science", 3, 24),
    # Fiction
    ("The Lost Kite", "Ayesha Noor", "Fiction", 2, 61),
    ("Journey to the Mountains", "Hamza Tariq", "Fiction", 1, 73),
    ("The Clever Merchant", "Rabia Aslam", "Fiction", 4, 38),
    ("Midnight in Lahore", "Usman Javed", "Fiction", 0, 66),
    ("The Secret Garden Door", "Zoya Malik", "Fiction", 3, 45),
    ("Adventures of a Young Pilot", "Danish Ali", "Fiction", 5, 22),
    ("The River Song", "Iqra Shah", "Fiction", 2, 52),
    ("Ghost of the Old School", "Talha Mirza", "Fiction", 1, 58),
    # History
    ("Ancient Civilizations", "Dr. Kamran Lodhi", "History", 3, 20),
    ("The Story of Pakistan", "Prof. Rashid Ahmed", "History", 4, 49),
    ("Great Empires of the World", "Sadia Farooq", "History", 2, 27),
    ("Famous Explorers", "Imran Khalid", "History", 0, 33),
    ("The Silk Road", "Laiba Hussain", "History", 5, 16),
    ("World War Stories for Students", "Adeel Chaudhry", "History", 1, 29),
    ("Inventions That Changed History", "Maha Yousuf", "History", 3, 35),
    ("Kings and Queens", "Rehan Butt", "History", 4, 14),
    # Technology
    ("Learn Python Step by Step", "Hassan Raza", "Technology", 2, 80),
    ("Introduction to Computers", "Fatima Saeed", "Technology", 5, 41),
    ("Safe Internet for Kids", "Zain Abbas", "Technology", 6, 18),
    ("Robots and the Future", "Dr. Salman Pervez", "Technology", 0, 64),
    ("Building Simple Websites", "Anaya Khan", "Technology", 3, 37),
    ("Data and Charts for Beginners", "Daniyal Sheikh", "Technology", 2, 44),
    ("Artificial Intelligence Basics", "Noor Fatima", "Technology", 1, 76),
    ("Fun with Electronics", "Waleed Iqbal", "Technology", 4, 26),
]

cursor.executemany(
    "INSERT INTO books (title, author, category, available_copies, times_borrowed) VALUES (?, ?, ?, ?, ?)",
    books,
)
connection.commit()

total = cursor.execute("SELECT COUNT(*) FROM books").fetchone()[0]
print(f"Database ready: {db_path}")
print(f"Total books: {total}")
for category, count, borrowed in cursor.execute(
    "SELECT category, COUNT(*), SUM(times_borrowed) FROM books GROUP BY category"
):
    print(f"  {category}: {count} books, {borrowed} borrowings")

connection.close()