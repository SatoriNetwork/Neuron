import sqlite3
import os
from typing import Dict, Any, List
from .uuid_generator import generateUUID
import pandas as pd
from pathlib import Path
from satorilib.logging import INFO, setup, debug, info, warning, error

setup(level=INFO)

# todo : pass the inputs as params for sql query
# todo : dataframe to sqlite
# todo : recieve data in database after client recieves data from server
# todo : check server.py for endpoint tasks



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
            # Execute CREATE TABLE statement
            self.cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS "{table_uuid}" (
                    ts TIMESTAMP PRIMARY KEY NOT NULL,
                    value NUMERIC(20, 10) NOT NULL,
                    hash TEXT NOT NULL
                )
            ''')
            self.conn.commit()
        except Exception as e:
            error(f"Table creation error for {table_uuid}: ", e)

    def sortTableByTimestamp(self, table_uuid: str):
        """Sort the existing rows in a table by timestamp."""
        try:
            # First drop temp table if it exists from a previous failed attempt
            temp_table = f'temp_{table_uuid}'
            self.cursor.execute(f'DROP TABLE IF EXISTS "{temp_table}"')
            
            # Create a temporary table with the same structure
            self.cursor.execute(f'''
                CREATE TABLE "{temp_table}" (
                    ts TIMESTAMP PRIMARY KEY NOT NULL,
                    value NUMERIC(20, 10) NOT NULL,
                    hash TEXT NOT NULL
                )
            ''')
            
            # Copy data from original table to temp table in sorted order
            self.cursor.execute(
                f'''
                INSERT INTO "{temp_table}" (ts, value, hash)
                SELECT ts, value, hash FROM "{table_uuid}"
                ORDER BY ts ASC
            ''')
            
            # Drop the original table
            self.cursor.execute(f'DROP TABLE IF EXISTS "{table_uuid}"')
            
            # Rename temp table to original name
            self.cursor.execute(f'ALTER TABLE "{temp_table}" RENAME TO "{table_uuid}"')
            
            self.conn.commit()
            info(f"Successfully sorted table {table_uuid} by timestamp")
            
        except Exception as e:
            error(f"Error sorting table {table_uuid}: {e}")
            # Clean up temp table if it exists
            try:
                self.cursor.execute(f'DROP TABLE IF EXISTS "{temp_table}"')
                self.conn.commit()
            except:
                pass
            self.conn.rollback()
            raise

    def deleteTable(self, table_uuid: str):
        try:
            self.cursor.execute(f'DROP TABLE IF EXISTS "{table_uuid}"')
            self.conn.commit()
        except Exception as e:
            error(f"Table deletion error for {table_uuid}:", e)

    def editTable(self, action: str, table_uuid: str, data: Dict[str, Any] = None, timestamp: str = None) -> Any:
        try:
            if action == 'insert':
                # Check for existing record with same values
                self.cursor.execute(f'SELECT ts FROM "{table_uuid}" WHERE ts = ?', (data['ts'],))
                existing = self.cursor.fetchone()
                
                if existing:
                    error(f"Record already exists with timestamp {existing[0]}")
                    raise sqlite3.IntegrityError(f"Record with timestamp {existing[0]} already exists")
                
                cols = ', '.join(data.keys())
                placeholders = ', '.join(['?' for _ in data])
                
                self.cursor.execute(f'INSERT INTO "{table_uuid}" ({cols}) VALUES ({placeholders})', list(data.values()))
                self.conn.commit()
                debug(f"Inserted new record into table {table_uuid}")

            # elif action == 'update':
            #     if not timestamp:
            #         raise ValueError("Timestamp is required for update operations")
                    
            #     sets = ', '.join([f"{k} = ?" for k in data.keys()])
            #     values = list(data.values()) + [timestamp]
            #     self.cursor.execute(f'UPDATE "{table_uuid}" SET {sets} WHERE ts = ?', values)

            elif action == 'delete':
                if not timestamp:
                    raise ValueError("Timestamp is required for delete operations")
                self.cursor.execute(f'DELETE FROM "{table_uuid}" WHERE ts = ?', (timestamp,))

            if self.cursor.rowcount == 0 and action != 'insert':
                raise ValueError(f"No record found with timestamp {timestamp}")
            
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
        finally:
            self.sortTableByTimestamp(table_uuid)
        
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
                        self.cursor.execute(
                            f'''
                            SELECT 1 FROM "{table_name}" WHERE ts = ? AND value = ? AND hash = ?
                            ''', (row['ts'], float(row['value']), str(row['hash'])))
                        result = self.cursor.fetchone()
                        
                        if not result:
                            # Insert only if not found
                            self.cursor.execute(f'INSERT INTO "{table_name}" (ts, value, hash) VALUES (?, ?, ?)', (row['ts'], float(row['value']), str(row['hash'])))
                    
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
        
    # confirm the inputs for this
    def import_csv(self, csv_path: str, readme_path: str):
        """
        Import a single CSV file with its associated readme metadata.
        
        Args:
            csv_path: Path to the CSV file
            readme_path: Path to the readme.md file containing metadata
        """
        try:
            # Parse readme and generate UUID
            stream_dict = self._parseReadme(Path(readme_path))
            if not stream_dict:
                error(f"Failed to parse readme file: {readme_path}")
                return
                
            table_uuid = generateUUID(stream_dict)
            
            # Create table if it doesn't exist
            self.createTable(table_uuid)
            
            # Read and process CSV
            df = pd.read_csv(csv_path, header=None, names=['ts', 'value', 'hash'])
            
            new_data_added = False
            imported_count = 0
            for _, row in df.iterrows():
                # Check for existing record
                self.cursor.execute(
                    f'''
                    SELECT 1 FROM "{table_uuid}" 
                    WHERE ts = ? AND value = ? AND hash = ?
                    ''', (
                        row['ts'], 
                        float(row['value']), 
                        str(row['hash'])
                    ))
                result = self.cursor.fetchone()
                
                if not result:
                    # Insert if record doesn't exist
                    self.cursor.execute(
                        f'''
                        INSERT INTO "{table_uuid}" (ts, value, hash) 
                        VALUES (?, ?, ?)
                        ''', (
                            row['ts'],
                            float(row['value']),
                            str(row['hash'])
                        ))
                    imported_count += 1
                    new_data_added = True
                    
            self.conn.commit()
             # Only sort if new data was added
            if new_data_added:
                info(f"New data was added, sorting table {table_uuid}")
                self.sortTableByTimestamp(table_uuid)
            else:
                info(f"No new data added to table {table_uuid}, skipping sort")
                
            return table_uuid
            
        except Exception as e:
            error(f"Error importing CSV {csv_path}: {e}")
            self.conn.rollback()
            return None

    def export_csv(self, table_uuid: str) -> Path:
        """
        Export data from a table to a CSV file.
        """
        try:
            # Create rec directory if it doesn't exist
            rec_dir = Path('rec')
            rec_dir.mkdir(exist_ok=True)
            
            # Query all data from the table
            df = pd.read_sql_query(
                f'''
                SELECT ts, value, hash 
                FROM "{table_uuid}" 
                ORDER BY ts
                ''', self.conn)
            
            if df.empty:
                warning(f"No data found in table {table_uuid}")
                return None
                
            # Export to CSV
            csv_path = rec_dir / f"{table_uuid}.csv"
            df.to_csv(csv_path, header=False, index=False)
            
            info(f"Exported {len(df)} rows to {csv_path}")
            return csv_path
            
        except Exception as e:
            error(f"Error exporting table {table_uuid}: {e}")
            return None

    def to_dataframe(self, table_uuid: str) -> pd.DataFrame:
        
        try:
            # Verify table exists
            self.cursor.execute(
                """
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name=?
                """, (table_uuid,))
            
            if not self.cursor.fetchone():
                raise ValueError(f"Table {table_uuid} does not exist")
                
            # Query all data from the table
            # todo pass the table_uuid as the param
            df = pd.read_sql_query(
                f"""
                SELECT ts, value, hash 
                FROM "{table_uuid}"
                ORDER BY ts
                """, self.conn)
            return df
            
        except ValueError as e:
            error(f"Table error: {e}")
            raise
        except Exception as e:
            error(f"Database error converting table {table_uuid} to DataFrame: {e}")
            raise


    # from dateframe to sqlite, inputs( table_uuid, df )
    def dataframeToDatabase(self, table_uuid: str, df: pd.DataFrame):
        try:
            # Verify table exists
            self.cursor.execute(
                """
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name=?
                """, (table_uuid,))
            
            if not self.cursor.fetchone():
                raise ValueError(f"Table {table_uuid} does not exist")
                
            # Validate DataFrame structure
            required_columns = {'ts', 'value', 'hash'}
            if not all(col in df.columns for col in required_columns):
                raise ValueError(f"DataFrame must contain columns: {required_columns}")
                
            # Convert value column to float
            df['value'] = df['value'].astype(float)
            
            # Convert hash column to string
            df['hash'] = df['hash'].astype(str)
            
            new_data_added = False
            imported_count = 0
            
            # Process each row
            for _, row in df.iterrows():
                # Check for existing record
                self.cursor.execute(
                    f'''
                    SELECT 1 FROM "{table_uuid}" 
                    WHERE ts = ? AND value = ? AND hash = ?
                    ''', (
                        row['ts'],
                        float(row['value']),
                        str(row['hash'])
                    ))
                result = self.cursor.fetchone()
                
                if not result:
                    # Insert if record doesn't exist
                    self.cursor.execute(
                        f'''
                        INSERT INTO "{table_uuid}" (ts, value, hash) 
                        VALUES (?, ?, ?)
                        ''', (
                            row['ts'],
                            float(row['value']),
                            str(row['hash'])
                        ))
                    imported_count += 1
                    new_data_added = True
                    
            self.conn.commit()
            
            # Sort table if new data was added
            if new_data_added:
                info(f"Added {imported_count} new records to table {table_uuid}, sorting table")
                self.sortTableByTimestamp(table_uuid)
            else:
                info(f"No new data added to table {table_uuid}, skipping sort")
                
            return True
            
        except ValueError as e:
            error(f"Validation error: {e}")
            self.conn.rollback()
            raise
        except Exception as e:
            error(f"Database error converting DataFrame to table {table_uuid}: {e}")
            self.conn.rollback()
            return False

## Testing
if __name__ == "__main__":
    db = SqliteDatabase()
    df=db.to_dataframe("23dc3133-5b3a-5b27-803e-70a07cf3c4f7")
    # print(df)
    # Example: dataframe to sql
    # table_uuid = "08b109cc-d62c-5e2a-a671-c382bc439311"
    # df = pd.DataFrame({
    #     'ts': ['2025-01-04 15:27:35'],
    #     'value': [123.45],
    #     'hash': ['abc123def456']
    # })
    # success = db.dataframeToDatabase(table_uuid, df)
    # db.importFromDataFolder()

    # Example: merge
    # new_row = pd.DataFrame({
    #         'ts': ['2024-12-01 05:45:00.658943'],  # Timestamp between the two rows
    #         'value': [78.0500],                     # Same value as surrounding rows
    #         'hash': ['abc123def456']                # Random hash similar to pattern
    #     })

    #     # Assuming your original DataFrame is called df
    #     # Insert the new row at position 22 (which will be between current rows 21 and 22)
    # df = pd.concat([df.iloc[:22], new_row, df.iloc[22:]]).reset_index(drop=True)
    # db.deleteTable("23dc3133-5b3a-5b27-803e-70a07cf3c4f7")
    # db.createTable("23dc3133-5b3a-5b27-803e-70a07cf3c4f7")
    # db.dataframeToDatabase("23dc3133-5b3a-5b27-803e-70a07cf3c4f7",new_row)

    # db.export_csv('23dc3133-5b3a-5b27-803e-70a07cf3c4f7')

    # db.import_csv('../../data/steeve/aggregate.csv','../../data/steeve/readme.md')

    # Example : Insert a new record
    # table_uuid ='08b109cc-d62c-5e2a-a671-c382bc439311'
    # data_to_insert = {
    #     'ts': '2025-01-04 15:27:35',
    #     'value': float(123.45),
    #     'hash': 'abc123def456'
    # }
    # db.editTable('insert', table_uuid, data_to_insert)

