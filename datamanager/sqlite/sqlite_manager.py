import sqlite3
import os
from typing import Dict, Any, List
from id_generator import generate_uuid
import pandas as pd
from pathlib import Path


## TODO

# At start-up
# scan all the folders inside data folder 
# take readme.md from each folder inside data folder  and store in a dictionary
# from the dictionary take the key = 'author' and 'stream' and generate_uuid 
# the generated UUID becomes the table_name
# using import_csv function, store values of csv in into sqlite

# export csv name will be table name

# check insertion of a single row into sqlite table ( table_name = generate_uuid( author, stream)) 
class SqliteDatabase:
    def __init__(self, data_dir: str = "../../data"):
        self.conn = None
        self.cursor = None
        self.dbname = "datafolder.db"
        self.data_dir = data_dir
        self.folder_metadata = self.get_folder_metadata()
        self.tables = self.generate_table_names()
        self.create_connection()
        self.create_all_tables()

    def parse_readme(self, readme_path: Path, folder_name: str) -> Dict[str, str]:
        """Parse README.md file containing JSON metadata."""
        import json
        
        try:
            with open(readme_path, 'r') as f:
                content = f.read().strip()
                if content:
                    json_data = json.loads(content)
                    if isinstance(json_data, dict):
                        return {
                            'source': json_data.get('source', ''),
                            'author': json_data.get('author', ''),
                            'stream': json_data.get('stream', ''),
                            'target': json_data.get('target', '')
                        }
        except Exception as e:
            print(f"Error parsing README {readme_path}: {e}")
        
        return {}
            

    def get_folder_metadata(self) -> Dict[str, Dict[str, str]]:
        """Scan all folders and extract metadata from README.md files."""
        metadata_dict = {}
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            print(f"Created data directory: {self.data_dir}")
            
        # print(f"Scanning directory: {self.data_dir}")
        for folder in os.listdir(self.data_dir):
            folder_path = Path(self.data_dir) / folder
            if folder_path.is_dir():
                # print(f"\nProcessing folder: {folder}")
                readme_path = folder_path / "readme.md"
                if readme_path.exists():  # Only process folders with readme.md
                    metadata = self.parse_readme(readme_path, folder)
                    if metadata.get('author') and metadata.get('stream'):  # Only include if required fields exist
                        metadata_dict[folder] = metadata
                        # print(f"Successfully added metadata for {folder}")
                        # print(f"Author: {metadata['author']}")
                        # print(f"Stream: {metadata['stream']}")
                    else:
                        print(f"Skipping {folder}: Missing required author or stream in readme.md")
                else:
                    print(f"Skipping {folder}: No readme.md found")
        
        # print(f"\nTotal folders processed: {len(metadata_dict)}")
        return metadata_dict

    def generate_table_names(self) -> Dict[str, str]:
        """Generate UUID-based table names from folder metadata.
        
        Returns:
            Dict[str, str]: A dictionary mapping folder names to their UUID-based table names
        """
        table_names = {}
        for folder, metadata in self.folder_metadata.items():
            # Create a dictionary with author and stream
            uuid_input = {
                'author': metadata.get('author', ''),
                'stream': metadata.get('stream', '')
            }
            table_names[folder] = generate_uuid(uuid_input)
        return table_names

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
        """Create table with proper column types and quotes around table name"""
        try:
            # Note the quotes around the table name and proper column types
            self.cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS "{table_name}" (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TIMESTAMP NOT NULL,
                    value NUMERIC(20, 10) NOT NULL,
                    hash TEXT NOT NULL
                )
            ''')
            self.conn.commit()
        except Exception as e:
            print(f"Table creation error for {table_name}:", e)

    def create_all_tables(self):
        for table in self.tables.values():
            self.create_table(table)
        self.import_csv()
    

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

    def import_csv(self):
        """
        Scan all folders in data directory and import their CSV files.
        Assumes CSV files have no headers and columns are in order: timestamp, value, hash
        """
        
        if not os.path.exists(self.data_dir):
            print(f"Data directory not found: {self.data_dir}")
            return
        
        imported_count = 0
        
        for folder_name in self.folder_metadata.keys():
            folder_path = Path(self.data_dir) / folder_name
            table_name = self.tables.get(folder_name)
            
            if not table_name:
                print(f"No table mapping found for folder: {folder_name}")
                continue
                
            csv_files = list(folder_path.glob('*.csv'))
            
            if not csv_files:
                continue
                
            for csv_file in csv_files:
                try:
                    # Read CSV with no headers
                    df = pd.read_csv(csv_file, header=None, names=['ts', 'value', 'hash'])
                    
                    for _, row in df.iterrows():
                        # Check if the record already exists
                        query_check = f'''
                        SELECT 1 FROM "{table_name}" WHERE ts = ? AND value = ? AND hash = ?
                        '''
                        self.cursor.execute(query_check, (row['ts'], float(row['value']), str(row['hash'])))
                        result = self.cursor.fetchone()
                        
                        if not result:
                            # Insert only if not found
                            query_insert = f'INSERT INTO "{table_name}" (ts, value, hash) VALUES (?, ?, ?)'
                            self.cursor.execute(query_insert, (row['ts'], float(row['value']), str(row['hash'])))
                    
                    self.conn.commit()
                    imported_count += 1
                except Exception as e:
                    print(f"Error importing {csv_file}: {e}")
                    self.conn.rollback()
                    continue
        
        print(f"\nImport complete. Successfully processed {imported_count} CSV files.")


    def export_csv(self):
        '''
        From the table inside the sqlite, a CSV file is produced in the required format
        '''
        # Create rec directory if it doesn't exist
        rec_dir = Path('rec')
        rec_dir.mkdir(exist_ok=True)

        exported_count = 0

        # Reverse the tables dictionary to get folder names from table IDs
        table_to_folder = {v: k for k, v in self.tables.items()}

        # for table_name in self.tables.values():
        table_name = '06a3aac1-a127-5c0f-8be9-9f44612fddd4'
    
        try:
            # Query all data from the table
            query = f'SELECT ts, value, hash FROM "{table_name}"'
            df = pd.read_sql_query(query, self.conn)
            if not df.empty:
                # Get the original folder name for this table
                folder_name = table_to_folder.get(table_name, table_name)
                
                # Create folder inside rec directory
                folder_path = rec_dir / folder_name
                folder_path.mkdir(exist_ok=True)
                # Export to CSV with table name (matching input format)
                csv_path = folder_path / f"{table_name}.csv"
                df.to_csv(csv_path, header=False, index=False)
                
                exported_count += 1
                print(f"Exported {len(df)} rows to {csv_path}")
        except Exception as e:
            print(f"Error exporting table {table_name}: {e}")
            # continue

        print(f"\nExport complete. Successfully exported {exported_count} tables to CSV files.")


## Testing
if __name__ == "__main__":
    db = SqliteDatabase()
    db.export_csv()

# Notes : 

# Find relation and create a UUID with a stream using values in the README inside each folder
