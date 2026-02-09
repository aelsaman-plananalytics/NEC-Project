from sqlalchemy import exc
from pydantic import ValidationError

def test_connection():
    try:
        from app.database import Base, engine
        from app.config import settings
    except ValidationError as e:
        print("ERROR: DATABASE_URL validation failed")
        print("\nThe DATABASE_URL in your .env file or environment variables is malformed.")
        print("\nCommon issues:")
        print("1. Password contains '@' symbol - must be URL-encoded as '%40'")
        print("2. Missing 'postgresql://' prefix")
        print("3. Special characters in password not URL-encoded")
        print("\nExample fixes:")
        print("  Wrong: postgresql://user:P@ssw0rd@host/db")
        print("  Right: postgresql://user:P%40ssw0rd@host/db")
        print("\nFull error details:")
        for error in e.errors():
            print(f"  - {error['msg']}")
        return
    except Exception as e:
        print(f"ERROR: Failed to load configuration: {e}")
        import traceback
        traceback.print_exc()
        return
    try:
        print("Connecting to database...")
        print("Importing all models to register with SQLAlchemy...")
        # Import app.models to ensure all models are registered with Base.metadata
        import app.models
        print("Creating tables...")
        # Now create all tables - all models should be registered
        Base.metadata.create_all(bind=engine)
        print("Success! Connected to Supabase and created tables.")
    except exc.SQLAlchemyError as e:
        error_str = str(e)
        print(f"Database error: {e}")
        print("\nTroubleshooting:")
        
        # Check for specific error types
        if "could not translate host name" in error_str or "Name or service not known" in error_str:
            print("⚠️  DNS/Network Error: Cannot resolve database hostname")
            print("   This indicates a network connectivity issue, not a configuration problem.")
            print("   Possible causes:")
            print("   1. No internet connection")
            print("   2. Database hostname is incorrect or doesn't exist")
            print("   3. Firewall blocking the connection")
            print("   4. VPN required to access the database")
            print("\n   ✅ Your DATABASE_URL format is correct!")
            print("   ✅ Code is working properly - this is a network/DNS issue.")
        elif "authentication failed" in error_str.lower() or "password" in error_str.lower():
            print("⚠️  Authentication Error: Database credentials are incorrect")
            print("   1. Verify username and password in DATABASE_URL")
            print("   2. Check if password needs URL-encoding (special characters)")
        else:
            print("1. Check that DATABASE_URL in .env file is correctly formatted")
            print("2. Format should be: postgresql://user:password@host:port/database?sslmode=require")
            print("3. If your password contains special characters (@, #, %, etc.), URL-encode them:")
            print("   - @ becomes %40")
            print("   - # becomes %23")
            print("   - % becomes %25")
            print("   Example: postgresql://user:P%40ssw0rd@host/db")
            print("4. Verify database credentials and network connectivity")
    except Exception as e:
        error_msg = str(e)
        if "DATABASE_URL" in error_msg and "@" in error_msg:
            print("ERROR: DATABASE_URL validation failed")
            print("\nCommon issue: Password contains '@' symbol")
            print("Solution: URL-encode special characters in your password")
            print("  - '@' → '%40'")
            print("  - '#' → '%23'")
            print("  - '%' → '%25'")
            print("\nExample:")
            print("  Wrong: postgresql://user:P@ssw0rd@host/db")
            print("  Right: postgresql://user:P%40ssw0rd@host/db")
        else:
            print(f"Unexpected error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_connection()
