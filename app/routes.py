"""
Frontend routes - serve HTML pages
These are registered in app/__init__.py to avoid circular imports
"""

from flask import render_template, send_from_directory, current_app, make_response, session, redirect, url_for
from werkzeug.exceptions import NotFound
from app.database.central_db import CentralDB
from sqlalchemy import text
from datetime import datetime
import os
import logging

logger = logging.getLogger(__name__)


def index():
    """Landing page with two doors"""
    try:
        response = make_response(render_template('landing.html'))
        # Prevent caching
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    except Exception as e:
        logger.error(f"Error rendering landing page: {e}", exc_info=True)
        return f"Error: {str(e)}", 500


def admin():
    """Admin dashboard - requires valid session"""
    try:
        # Check if user has valid session
        session_token = session.get('session_token')
        user_id = session.get('user_id')
        user_role = session.get('role')
        
        if not session_token or not user_id:
            return redirect('/')
        
        # Verify session in database
        db_session = CentralDB.get_session()
        result = db_session.execute(
            text("""
                SELECT user_id, expires_at 
                FROM user_sessions 
                WHERE session_token = :token AND user_id = :user_id
            """),
            {'token': session_token, 'user_id': user_id}
        )
        session_data = result.fetchone()
        db_session.close()
        
        if not session_data or session_data.expires_at < datetime.utcnow():
            # Invalid or expired session - clear and redirect
            session.clear()
            return redirect('/')
        
        # Check role
        if user_role != 'admin':
            return redirect('/')
        
        response = make_response(render_template('admin.html'))
        # Prevent caching of protected pages
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, private'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response
    except Exception as e:
        logger.error(f"Error rendering admin page: {e}", exc_info=True)
        session.clear()
        return redirect('/login')


def depot():
    """Depot dashboard - requires valid session"""
    try:
        # Check if user has valid session
        session_token = session.get('session_token')
        user_id = session.get('user_id')
        user_role = session.get('role')
        
        if not session_token or not user_id:
            return redirect('/')
        
        # Verify session in database
        db_session = CentralDB.get_session()
        result = db_session.execute(
            text("""
                SELECT user_id, expires_at 
                FROM user_sessions 
                WHERE session_token = :token AND user_id = :user_id
            """),
            {'token': session_token, 'user_id': user_id}
        )
        session_data = result.fetchone()
        db_session.close()
        
        if not session_data or session_data.expires_at < datetime.utcnow():
            # Invalid or expired session - clear and redirect
            session.clear()
            return redirect('/')
        
        # Check role
        if user_role != 'depot':
            return redirect('/')
        
        response = make_response(render_template('depot.html'))
        # Prevent caching of protected pages
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, private'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response
    except Exception as e:
        logger.error(f"Error rendering depot page: {e}", exc_info=True)
        session.clear()
        return redirect('/login')




def static_files(filename):
    """Serve static files"""
    try:
        # Get static folder from current app
        static_folder = current_app.static_folder
        return send_from_directory(static_folder, filename)
    except Exception as e:
        return f"Error serving static file: {str(e)}", 500
