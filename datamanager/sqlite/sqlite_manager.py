import sqlite3
import os
from typing import Dict, Any, List
from uuid_generator import generateUUID
import pandas as pd
from pathlib import Path
from satorilib.logging import INFO, setup, debug, info, warning, error

setup(level=DEBUG)

## TODO

    # refactor sqlite class
    # use UUID to transfer data be client and server
    # Should we use id or timestamps as the PK? ( clarify ) 


class SqliteDatabase:
    def __init__(self, data_dir: str = "../../data"):
        self.conn = None
        self.cursor = None
        self.data_dir = data_dir
        self.dbname = os.path.join(data_dir, "data.db")
        self.createConnection()

    def importFromDataFolder(self):
        def _getStreamInfoFromFolder() -> Dict:
            """Scan all folders and extract stream info from README.md files."""
            stream_infos = {}
            if not os.path.exists(self.data_dir):
                error("Data Folder does not exists")
            for folder in os.listdir(self.data_dir):
                folder_path = Path(self.data_dir) / folder
                if folder_path.is_dir():
                    readme_path = folder_path / "readme.md"
                    if readme_path.exists(): 
                        stream_info = self._parseReadme(readme_path)
                        stream_infos[folder] = stream_info
                    else:
                        error(f"Skipping {folder}: No readme.md found")
            return stream_infos
        
        folder_stream_info = _getStreamInfoFromFolder()
        table_uuids = {folder: generateUUID(streaminfo) for folder, streaminfo in folder_stream_info.items()}
        for table_uuid in table_uuids.values():
            self.createTable(table_uuid)
        self.importCSVFromDataFolder(folder_stream_info, table_uuids)

    def createConnection(self):
        try:
            if self.conn:
                self.conn.close()
            info(f"Connecting to database at: {self.dbname}")
            os.makedirs(os.path.dirname(self.dbname), exist_ok=True)
            self.conn = sqlite3.connect(self.dbname)
            self.cursor = self.conn.cursor()
            self.cursor.execute('PRAGMA foreign_keys = ON;')
            self.cursor.execute('PRAGMA journal_mode = WAL;')
            self.cursor.execute('SELECT sqlite_version()')
        except Exception as e:
            error("Connection error:", e)

    def disconnect(self):
        if self.cursor:
            self.cursor.close()
            self.conn.close()

    def deleteDatabase(self):
        try:
            self.disconnect()
            if os.path.exists(self.dbname):
                os.remove(self.dbname)
        except Exception as e:
            error("Delete error:", e)

    def createTable(self, table_uuid: str):
        """Create table with proper column types and quotes around table name"""
        try:
            # Note the quotes around the table name and proper column types
            self.cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS "{table_uuid}" (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TIMESTAMP NOT NULL,
                    value NUMERIC(20, 10) NOT NULL,
                    hash TEXT NOT NULL
                )
            ''')
            self.conn.commit()
        except Exception as e:
            error(f"Table creation error for {table_uuid}: ", e)

    def deleteTable(self, table_uuid: str):
        try:
            self.cursor.execute(f"DROP TABLE IF EXISTS {table_uuid}")
            self.conn.commit()
        except Exception as e:
            error(f"Table deletion error for {table_uuid}:", e)

    def editTable(self, action: str, table_uuid: str, data: Dict[str, Any] = None, id_: int = None) -> Any:
        try:
            if action == 'insert':
                # Check for existing record with same values
                where_clause = ' AND '.join([f"{k} = ?" for k in data.keys()])
                check_query = f'SELECT id FROM "{table_uuid}" WHERE {where_clause}'
                self.cursor.execute(check_query, list(data.values()))
                existing = self.cursor.fetchone()
                
                if existing:
                    error(f"Record already exists with id {existing[0]}")
                    return existing[0]
                
                cols = ', '.join(data.keys())
                placeholders = ', '.join(['?' for _ in data])
                insert_query = f'INSERT INTO "{table_uuid}" ({cols}) VALUES ({placeholders})'
                
                self.cursor.execute(insert_query, list(data.values()))
                new_id = self.cursor.lastrowid
                self.conn.commit()
                debug(f"Inserted new record with id {new_id}")
                return new_id

            elif action == 'update':
                sets = ', '.join([f"{k} = ?" for k in data.keys()])
                values = list(data.values()) + [id_]
                self.cursor.execute(f'UPDATE "{table_uuid}" SET {sets} WHERE id = ?', values)

            elif action == 'delete':
                self.cursor.execute(f'DELETE FROM "{table_uuid}" WHERE id = ?', (id_,))

            if self.cursor.rowcount == 0 and action != 'insert':
                raise ValueError(f"No record found with id {id_}")
            
            self.conn.commit()
            return None
                
        except sqlite3.IntegrityError as e:
            error(f"Database integrity error: {e}")
            self.conn.rollback()
            raise
        except Exception as e:
            error(f"{action.capitalize()} error for {table_uuid}: {e}")
            self.conn.rollback()
            raise
        
    def importCSVFromDataFolder(self, folder_metadata: dict, table_uuids: str):
        """
        Scan all folders in data directory and import their CSV files.
        Assumes CSV files have no headers and columns are in order: timestamp, value, hash
        """
        
        if not os.path.exists(self.data_dir):
            print(f"Data directory not found: {self.data_dir}")
            return
        
        imported_count = 0
        
        for folder_name in folder_metadata.keys():
            folder_path = Path(self.data_dir) / folder_name
            table_name = table_uuids.get(folder_name)
            
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
    
    def _parseReadme(self, readme_path: Path) -> Dict[str, str]:
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
            error(f"Error parsing README {readme_path}: {e}")
            return {}
        
    # todo: 
    # import csv (self, csv, readme_path):
    #   stream_dict = self._parseReadme(readme_path)
    #   table_uuid = generateUUID(stream_dict)
    #   self.createTable(table_uuid)
        # df = pd.read_csv(csv, header=None, names=['ts', 'value', 'hash']) 
        # for _, row in df.iterrows():
        #     # Check if the record already exists
        #     query_check = f'''
        #     SELECT 1 FROM "{table_name}" WHERE ts = ? AND value = ? AND hash = ?
        #     '''
        #     self.cursor.execute(query_check, (row['ts'], float(row['value']), str(row['hash'])))
        #     result = self.cursor.fetchone()


    # todo:  requires only UUID as input and csv is produced
    def _exportCSV(self, table_name: str):
        '''
        From the table inside the sqlite, a CSV file is produced in the required format
        '''
        # Create rec directory if it doesn't exist
        rec_dir = Path('rec')
        rec_dir.mkdir(exist_ok=True)

        exported_count = 0

        # Reverse the tables dictionary to get folder names from table IDs
        table_to_folder = {v: k for k, v in self.tables.items()}
    
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
    db.importFromDataFolder()
    # db.export_csv('77a2da56-80b5-5ed4-b133-727d06b17ed4')
    #Example 1:insert a row
    # data_to_insert = {
    #     'ts': '2025-01-04 15:27:35',
    #     'value': float(123.45),
    #     'hash': 'abc123def456'
    # }
    # table_name = '0b63267e-4bf3-5815-8b45-a5d41a2cebb0'
    # db.edit_table(table_name, 'insert', data_to_insert)
    # Example 2: Update the row we just inserted
    # update_data = {
    #     'value': float(999.99),
    #     'hash': 'updated_hash'
    # }
    # db.edit_table(table_name, 'update', update_data, 2)
    
    # Example 3: Delete the row
    # db.edit_table(table_name, 'delete', id_=2)
    # db.export_csv()

