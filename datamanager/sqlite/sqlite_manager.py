import sqlite3
import os
from typing import Dict, Any, List
from Neuron.datamanager.sqlite.uuid import generate_uuid

class SqliteDatabase:
    def __init__(self, data_dir: str = "../../data"):
        self.conn = None
        self.cursor = None
        self.dbname = "datafolder.db"
        self.data_dir = data_dir
        self.tables = self.get_folder_names()
        self.create_connection()
        self.create_all_tables()

    def get_folder_names(self) -> List[str]:
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
        return [d for d in os.listdir(self.data_dir) 
                if os.path.isdir(os.path.join(self.data_dir, d))]

    def create_connection(self):
        try:
            if self.conn:
                self.conn.close()
            self.conn = sqlite3.connect(self.dbname)
            self.cursor = self.conn.cursor()
        except Exception as e:
            print("Connection error:", e)

    def disconnect(self):
        if self.cursor:
            self.cursor.close()
            self.conn.close()

    def delete_database(self):
        try:
            self.disconnect()
            if os.path.exists(self.dbname):
                os.remove(self.dbname)
        except Exception as e:
            print("Delete error:", e)

    def create_table(self, table_name: str):
        try:
            self.cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS "{table_name}" (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TIMESTAMP,
                    value DECIMAL(10,10),
                    hash VARCHAR(32)
                )
            """)
            self.conn.commit()
        except Exception as e:
            print(f"Table creation error for {table_name}:", e)

    def create_all_tables(self):
        for table in self.tables:
            self.create_table(table)

    def delete_table(self, table_name: str):
        try:
            self.cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
            self.conn.commit()
        except Exception as e:
            print(f"Table deletion error for {table_name}:", e)

    def edit_table(self, table_name: str, action: str, data: Dict[str, Any] = None, id_: int = None):
        try:
            if action == 'insert':
                cols = ', '.join(data.keys())
                placeholders = ', '.join(['?' for _ in data])
                self.cursor.execute(f"INSERT INTO {table_name} ({cols}) VALUES ({placeholders})", list(data.values()))
                return self.cursor.lastrowid

            elif action == 'update':
                sets = ', '.join([f"{k} = ?" for k in data.keys()])
                values = list(data.values()) + [id_]
                self.cursor.execute(f"UPDATE {table_name} SET {sets} WHERE id = ?", values)

            elif action == 'delete':
                self.cursor.execute(f"DELETE FROM {table_name} WHERE id = ?", (id_,))

            if self.cursor.rowcount == 0:
                raise ValueError(f"No record found with id {id_}")
            
            self.conn.commit()
            
        except Exception as e:
            print(f"{action.capitalize()} error for {table_name}:", e)

    def import_csv():
        '''
        Take a CSV as input and store after creating a UUID as the table name and then take values
        from the CSV and store it inside the db
        '''
        pass

    def export_csv():
        '''
        From the table inside the sqlite, a CSV file is produced in the required format
        '''
        pass


## Testing

db = SqliteDatabase()


# Notes : 

# Find relation and create a UUID with a stream using values in the README inside each folder