import React, { useState } from 'react';

const SourceReference = ({ source }) => {
  const [expanded, setExpanded] = useState(false);

  const highlightText = (text, highlighted) => {
    if (!highlighted) return text;
    
    const parts = text.split(highlighted);
    return (
      <>
        {parts.map((part, i) => (
          <React.Fragment key={i}>
            {part}
            {i < parts.length - 1 && (
              <mark className="bg-yellow-200 px-1 rounded">{highlighted}</mark>
            )}
          </React.Fragment>
        ))}
      </>
    );
  };

  return (
    <div className="bg-gray-50 rounded-md p-3 text-sm">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <svg
              className="w-4 h-4 text-blue-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"
              />
            </svg>
            <span className="font-semibold text-gray-700">
              {source.filename}
            </span>
            {source.page_number && (
              <span className="text-gray-500">• Page {source.page_number}</span>
            )}
          </div>

          {expanded && (
            <div className="mt-2 p-2 bg-white rounded border border-gray-200 text-gray-700">
              {highlightText(source.text, source.highlighted_text)}
            </div>
          )}
        </div>

        <button
          onClick={() => setExpanded(!expanded)}
          className="ml-2 text-blue-600 hover:text-blue-800 text-xs font-medium"
        >
          {expanded ? 'Masquer' : 'Voir'}
        </button>
      </div>

      {source.highlighted_text && !expanded && (
        <div className="mt-1 text-gray-600 italic line-clamp-2">
          "{source.highlighted_text}..."
        </div>
      )}
    </div>
  );
};

export default SourceReference;