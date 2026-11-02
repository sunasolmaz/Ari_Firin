import sys
import psycopg2

sys.stdout.reconfigure(encoding='utf-8')

def update_branches(host):
    try:
        conn = psycopg2.connect(
            host=host,
            port=5432,
            dbname='accounting_db',
            user='postgres',
            password='Solmaz142',
            connect_timeout=5
        )
        cur = conn.cursor()
        print(f"Connecting to {host}...")
        
        # Check current branches
        cur.execute("SELECT id, name, city, address FROM branches ORDER BY id;")
        print("Before update:", cur.fetchall())
        
        # Update branches 1, 2, 3
        updates = [
            (1, 'Armada', 'Tekirdağ', 'Çorlu'),
            (2, 'Çobançeşme', 'Tekirdağ', 'Çorlu'),
            (3, 'Rumeli', 'Tekirdağ', 'Çorlu')
        ]
        for b_id, name, city, address in updates:
            cur.execute("""
                UPDATE branches 
                SET name = %s, city = %s, address = %s, updated_at = CURRENT_TIMESTAMP 
                WHERE id = %s
            """, (name, city, address, b_id))
            
        conn.commit()
        
        # Ensure Orion Şube exists
        cur.execute("""
            INSERT INTO branches (name, city, address, branch_type, is_active)
            SELECT 'Orion Şube', 'Tekirdağ', 'Çorlu', 'retail', TRUE
            WHERE NOT EXISTS (SELECT 1 FROM branches WHERE LOWER(name) LIKE '%%orion%%');
        """)
        conn.commit()
        
        cur.execute("SELECT id, name, city, address, is_active FROM branches ORDER BY id;")
        print("After update:", cur.fetchall())
        conn.close()
        print(f"Successfully updated branches on {host}!\n")
    except Exception as e:
        print(f"Error on {host}: {e}\n")

if __name__ == '__main__':
    # Update on Raspberry Pi central server
    update_branches('192.168.1.182')
