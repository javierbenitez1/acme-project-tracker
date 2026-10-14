import { useState } from 'react';

const flatten = (details) => Object.fromEntries(
  Object.entries(details || {}).map(([key, value]) => {
    if (typeof value === 'string') return [key, value];
    if (Array.isArray(value)) return [key, value.join(', ')];
    if (value && typeof value === 'object') return [key, Object.values(value).join(' ')];
    return [key, undefined];
  }),
);

/** Form values plus field-level errors from the client or the server, shared by every form in the app. */
export default function useFormState(initial) {
  const [values, setValues] = useState(initial);
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState('');

  const set = (name, value) => {
    setValues((current) => ({ ...current, [name]: value }));
    setErrors((current) => ({ ...current, [name]: undefined }));
  };

  const field = (name, hint) => ({
    name,
    value: values[name] ?? '',
    onChange: (event) => set(name, event.target.value),
    error: Boolean(errors[name]),
    helperText: errors[name] || hint,
  });

  /** rules: { fieldName: errorMessage or false }. Returns true when every rule passes. */
  const check = (rules) => {
    const next = Object.fromEntries(Object.entries(rules).filter(([, message]) => message));
    setErrors(next);
    setFormError('');
    return Object.keys(next).length === 0;
  };

  const fail = (error) => {
    setFormError(error.message);
    setErrors(flatten(error.details));
  };

  return { values, set, field, errors, formError, setFormError, check, fail };
}