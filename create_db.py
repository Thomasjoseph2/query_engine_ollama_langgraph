import psycopg2
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Database connection details from environment variables
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

# Ensure environment variables are set
if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME]):
    raise ValueError("Missing one or more required environment variables for DB connection.")

# Connect to PostgreSQL Database
conn = psycopg2.connect(
    user=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME
)
conn.autocommit = True
cursor = conn.cursor()

# Drop existing tables
drop_table_queries = [
    "DROP TABLE IF EXISTS financials CASCADE",
    "DROP TABLE IF EXISTS assets CASCADE",
    "DROP TABLE IF EXISTS assets_maintenance CASCADE",
    "DROP TABLE IF EXISTS cradles CASCADE",
    "DROP TABLE IF EXISTS vessels CASCADE",
    "DROP TABLE IF EXISTS inventory CASCADE",
    "DROP TABLE IF EXISTS trolleys CASCADE",
    "DROP TABLE IF EXISTS lifts CASCADE",
    "DROP TABLE IF EXISTS work_orders CASCADE",
    "DROP TABLE IF EXISTS wheels_load CASCADE",
    "DROP TABLE IF EXISTS rails CASCADE",
    "DROP TABLE IF EXISTS wheels_temperature CASCADE",
]

for query in drop_table_queries:
    try:
        cursor.execute(query)
        print(f"Table dropped successfully: {query.split()[3]}")
    except psycopg2.Error as e:
        print(f"Error dropping table: {query.split()[3]} - {e}")

create_table_queries = [

    """
    CREATE TABLE assets (
        id VARCHAR(100) PRIMARY KEY,
        assetType VARCHAR(100),
        name VARCHAR(100),
        description VARCHAR(255),
        status VARCHAR(50),
        createdAt TIMESTAMP,
        updatedAt TIMESTAMP
    )
    """,
"""
CREATE TABLE financials (
    id VARCHAR(100) PRIMARY KEY,
    recordDate DATE NOT NULL,
    dockingFees NUMERIC DEFAULT 0 NOT NULL,              
    onDockingFees NUMERIC DEFAULT 0 NOT NULL,            
    undockingFees NUMERIC DEFAULT 0 NOT NULL,            
    maintenanceFees NUMERIC DEFAULT 0 NOT NULL,          
    otherServiceFees NUMERIC DEFAULT 0 NOT NULL,        

    totalRevenue NUMERIC DEFAULT 0 NOT NULL,  

    laborCosts NUMERIC DEFAULT 0 NOT NULL,              
    dockOperationCosts NUMERIC DEFAULT 0 NOT NULL,       
    equipmentCosts NUMERIC DEFAULT 0 NOT NULL,          
    administrativeCosts NUMERIC DEFAULT 0 NOT NULL,   

    totalExpenses NUMERIC DEFAULT 0 NOT NULL,  
    netProfitLoss NUMERIC DEFAULT 0 NOT NULL,   

    assetId VARCHAR(100),
    CONSTRAINT fkFinancialsAssetId FOREIGN KEY (assetId) REFERENCES assets(id)
)
"""
,
    """
    CREATE TABLE cradles (
        id VARCHAR(100) PRIMARY KEY,
        updatedAt TIMESTAMP,
        cradleName VARCHAR(100),
        capacity NUMERIC,
        maxShipLength NUMERIC,
        status VARCHAR(50),
        location VARCHAR(100),
        lastMaintenanceDate TIMESTAMP,
        nextMaintenanceDue TIMESTAMP,
        operationalSince TIMESTAMP,
        notes VARCHAR(255),
        occupancy VARCHAR(100),
        currentLoad NUMERIC,
        structuralStress VARCHAR(50),
        wearLevel VARCHAR(50),
        assetId VARCHAR(100),
        CONSTRAINT fkCradleAssetId FOREIGN KEY (assetId) REFERENCES assets(id)
    )
    """,
    """
    CREATE TABLE vessels (
        id VARCHAR(100) PRIMARY KEY,
        updatedAt TIMESTAMP,
        vesselName VARCHAR(100) UNIQUE,
        vesselType VARCHAR(50),
        weight NUMERIC,
        length NUMERIC,
        width NUMERIC,
        draft NUMERIC,
        status VARCHAR(50),
        lastMaintenanceDate TIMESTAMP,
        nextMaintenanceDue TIMESTAMP,
        birthingArea VARCHAR(100),
        operationalSince TIMESTAMP,
        ownerCompany VARCHAR(100),
        notes VARCHAR(255),
        assignedCradle VARCHAR(100),
        transferCompleted VARCHAR(50),
        estimatedTimeToDestination VARCHAR(50),
        bearingTemperature NUMERIC,
        assetId VARCHAR(100),
        CONSTRAINT fkVesselAssetId FOREIGN KEY (assetId) REFERENCES assets(id),
        CONSTRAINT fkVesselAssignedCradle FOREIGN KEY (assignedCradle) REFERENCES cradles(id)
    )
    """,
    """
    CREATE TABLE inventory (
        id VARCHAR(100) PRIMARY KEY,
        updatedAt TIMESTAMP,
        lastUpdated TIMESTAMP,
        name VARCHAR(100),
        location VARCHAR(100),
        quantity NUMERIC,
        assetId VARCHAR(100),
        CONSTRAINT fkInventoryAssetId FOREIGN KEY (assetId) REFERENCES assets(id)
    )
    """,
    """
    CREATE TABLE rails (
        id VARCHAR(100) PRIMARY KEY,
        updatedAt TIMESTAMP,
        railName VARCHAR(100),
        length NUMERIC,
        capacity NUMERIC,
        status VARCHAR(50),
        lastInspectionDate TIMESTAMP,
        nextInspectionDue TIMESTAMP,
        operationalSince TIMESTAMP,
        notes VARCHAR(255),
        assetId VARCHAR(100),
        CONSTRAINT fkRailAssetId FOREIGN KEY (assetId) REFERENCES assets(id)
    )
    """,
    """
    CREATE TABLE trolleys (
        id VARCHAR(100) PRIMARY KEY,
        updatedAt TIMESTAMP,
        trolleyName VARCHAR(100),
        wheelCount NUMERIC,
        railId VARCHAR(100),
        assignedVesselId VARCHAR(100),
        status VARCHAR(50),
        lastMaintenanceDate TIMESTAMP,
        nextMaintenanceDue TIMESTAMP,
        notes VARCHAR(255),
        maxCapacity NUMERIC,
        currentLoad NUMERIC,
        speed NUMERIC,
        location VARCHAR(255),
        utilizationRate VARCHAR(50),
        averageTransferTime VARCHAR(50),
        assetId VARCHAR(100),
        CONSTRAINT fkTrolleyAssetId FOREIGN KEY (assetId) REFERENCES assets(id),
        CONSTRAINT fkTrolleyRailId FOREIGN KEY (railId) REFERENCES rails(id),
        CONSTRAINT fkTrolleyAssignedVesselId FOREIGN KEY (assignedVesselId) REFERENCES vessels(id)
    )
    """,
    """
    CREATE TABLE lifts (
        id VARCHAR(100) PRIMARY KEY,
        updatedAt TIMESTAMP,
        liftName VARCHAR(100),
        platformLength NUMERIC,
        platformWidth NUMERIC,
        maxShipDraft NUMERIC,
        location VARCHAR(255),
        status VARCHAR(50),
        lastMaintenanceDate TIMESTAMP,
        nextMaintenanceDue TIMESTAMP,
        operationalSince TIMESTAMP,
        assignedVesselId VARCHAR(100),
        notes VARCHAR(255),
        currentLoad NUMERIC,
        historicalUsageHours NUMERIC,
        maxCapacity NUMERIC,
        utilizationRate VARCHAR(50),
        averageTransferTime VARCHAR(50),
        assetId VARCHAR(100),
        CONSTRAINT fkLiftAssetId FOREIGN KEY (assetId) REFERENCES assets(id),
        CONSTRAINT fkLiftAssignedVesselId FOREIGN KEY (assignedVesselId) REFERENCES vessels(id)
    )
    """,
    """
    CREATE TABLE assets_maintenance (
        id VARCHAR(100) PRIMARY KEY,
        updatedAt TIMESTAMP,
        assetId VARCHAR(100),
        description VARCHAR(255),
        datePerformed TIMESTAMP,
        performedBy VARCHAR(255),
        nextDueDate TIMESTAMP,
        assetName VARCHAR(100),
        historicalUsageHours NUMERIC,
        remainingLifespanHours NUMERIC,
        statusSummary VARCHAR(255),
        shipsInTransfer NUMERIC,
        operationalLifts NUMERIC,
        operationalTrolleys NUMERIC,
        CONSTRAINT fkMmaintenanceAssetId FOREIGN KEY (assetId) REFERENCES assets(id)
    )
    """,
    """
    CREATE TABLE work_orders (
        id VARCHAR(100) PRIMARY KEY,
        updatedAt TIMESTAMP,
        workType VARCHAR(50),
        assignedTo VARCHAR(100),
        startDate TIMESTAMP,
        endDate TIMESTAMP,
        status VARCHAR(50),
        notes VARCHAR(255),
        vesselName VARCHAR(100),
        vesselId VARCHAR(100), 
        CONSTRAINT fkWorkOrderVesselId FOREIGN KEY (vesselId) REFERENCES vessels(id)   
    )
    """,
    """
    CREATE TABLE wheels_load (
        id VARCHAR(100) PRIMARY KEY,
        updatedAt TIMESTAMP,
        trolley VARCHAR(100),
        wheel VARCHAR(100),
        currentLoad NUMERIC,
        CONSTRAINT fkWheelsLoadTrolleyId FOREIGN KEY (trolley) REFERENCES trolleys(id)
    )
    """,
    """
    CREATE TABLE wheels_temperature (
        id VARCHAR(100) PRIMARY KEY,
        updatedAt TIMESTAMP,
        trolley VARCHAR(100),
        wheel VARCHAR(100),
        bearingTemperature NUMERIC,
        CONSTRAINT fkWheelsTempTrolley_id FOREIGN KEY (trolley) REFERENCES trolleys(id)
    )
    """
]

# Execute table creation queries
for query in create_table_queries:
    try:
        cursor.execute(query)
        print(f"Table created successfully: {query.split()[2]}")
    except psycopg2.Error as e:
        print(f"Error creating table: {query.split()[2]} - {e}")

# Close connection
cursor.close()
conn.close()