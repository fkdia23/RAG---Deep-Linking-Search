import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const DocumentUpload = () => {
  const [documents, setDocuments] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [urlInput, setUrlInput] = useState('');
  const [message, setMessage] = useState(null);

  useEffect(() => {
    fetchDocuments();
  }, []);

  const fetchDocuments = async () => {
    try {
      const response = await axios.get(`${API_URL}/documents`);
      setDocuments(response.data.documents);
    } catch (error) {
      console.error('Error fetching documents:', error);
    }
  };

  const handleFileUpload = async (e) => {
    const files = Array.from(e.target.files);
    if (files.length === 0) return;

    setUploading(true);
    setMessage(null);

    try {
      for (const file of files) {
        const formData = new FormData();
        formData.append('file', file);

        await axios.post(`${API_URL}/upload/file`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });
      }

      setMessage({
        type: 'success',
        text: `${files.length} document(s) importé(s) avec succès`
      });
      fetchDocuments();
    } catch (error) {
      setMessage({
        type: 'error',
        text: `Erreur lors de l'import: ${error.response?.data?.detail || error.message}`
      });
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  const handleUrlUpload = async (e) => {
    e.preventDefault();
    if (!urlInput.trim()) return;

    setUploading(true);
    setMessage(null);

    try {
      await axios.post(`${API_URL}/upload/url`, { url: urlInput });
      setMessage({
        type: 'success',
        text: 'Document importé depuis l\'URL avec succès'
      });
      setUrlInput('');
      fetchDocuments();
    } catch (error) {
      setMessage({
        type: 'error',
        text: `Erreur: ${error.response?.data?.detail || error.message}`
      });
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (filename) => {
    if (!window.confirm(`Supprimer "${filename}" ?`)) return;

    try {
      await axios.delete(`${API_URL}/documents/${encodeURIComponent(filename)}`);
      setMessage({
        type: 'success',
        text: 'Document supprimé'
      });
      fetchDocuments();
    } catch (error) {
      setMessage({
        type: 'error',
        text: `Erreur: ${error.response?.data?.detail || error.message}`
      });
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Messages */}
      {message && (
        <div
          className={`p-4 rounded-lg ${
            message.type === 'success'
              ? 'bg-green-100 text-green-800'
              : 'bg-red-100 text-red-800'
          }`}
        >
          {message.text}
        </div>
      )}

      {/* Upload Section */}
      <div className="bg-white rounded-lg shadow p-6 space-y-4">
        <h2 className="text-xl font-bold text-gray-800">Importer des documents</h2>

        {/* File Upload */}
        <div>
          <label className="block mb-2 text-sm font-medium text-gray-700">
            Fichiers locaux (PDF, TXT, DOCX)
          </label>
          <input
            type="file"
            multiple
            accept=".pdf,.txt,.docx,.doc"
            onChange={handleFileUpload}
            disabled={uploading}
            className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 disabled:opacity-50"
          />
        </div>

        {/* URL Upload */}
        <div>
          <label className="block mb-2 text-sm font-medium text-gray-700">
            Importer depuis une URL
          </label>
          <form onSubmit={handleUrlUpload} className="flex gap-2">
            <input
              type="url"
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              placeholder="https://example.com/document.pdf"
              disabled={uploading}
              className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={uploading || !urlInput.trim()}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
            >
              {uploading ? 'Import...' : 'Importer'}
            </button>
          </form>
        </div>
      </div>

      {/* Documents List */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-bold text-gray-800 mb-4">
          Documents importés ({documents.length})
        </h2>

        {documents.length === 0 ? (
          <p className="text-gray-500 text-center py-8">
            Aucun document importé
          </p>
        ) : (
          <div className="space-y-2">
            {documents.map((doc, index) => (
              <div
                key={index}
                className="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100"
              >
                <div className="flex items-center gap-3 flex-1">
                  <svg
                    className="w-5 h-5 text-blue-600"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                    />
                  </svg>
                  <div>
                    <p className="font-medium text-gray-800">{doc.filename}</p>
                    <p className="text-sm text-gray-500">
                      {doc.chunk_count} chunks • {new Date(doc.created_at).toLocaleDateString('fr-FR')}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => handleDelete(doc.filename)}
                  className="text-red-600 hover:text-red-800 p-2"
                  title="Supprimer"
                >
                  <svg
                    className="w-5 h-5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                    />
                  </svg>
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default DocumentUpload;