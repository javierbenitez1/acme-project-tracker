import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useToast } from '../components/Toast';
import { describeError } from '../utils/errors';

/** Everything that could show changed data. Refreshing them all keeps every screen consistent after a save. */
const REFRESH = ['project', 'projects', 'milestones', 'deliverables', 'budgets', 'dashboard', 'actions', 'users', 'schedule'];

/** Runs an API write, refreshes affected screens, and reports the outcome in a toast. */
export default function useApiMutation(mutationFn, { success, onSuccess, onError } = {}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn,
    onSuccess: (data, variables) => {
      REFRESH.forEach((key) => queryClient.invalidateQueries({ queryKey: [key] }));
      if (data?.warning) {
        toast.info(data.warning);
      } else {
        const message = typeof success === 'function' ? success(data, variables) : success;
        if (message) toast.success(message);
      }
      onSuccess?.(data, variables);
    },
    onError: onError || ((error) => toast.error(describeError(error))),
  });
}