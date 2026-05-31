import { useState } from 'react';
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query';
import { toast } from 'sonner';

import { extractErrorMessage } from '@/api/client';
import type { Paginated } from '@/api/types';

interface Options<T> {
  queryKey: readonly unknown[];
  fetcher: (params: Record<string, unknown>) => Promise<Paginated<T>>;
  deleter?: (id: string) => Promise<unknown>;
  pageSize?: number;
}

export function useCrudList<T extends { id: string }>({ queryKey, fetcher, deleter, pageSize = 25 }: Options<T>) {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');

  const params: Record<string, unknown> = { page, page_size: pageSize };
  if (search.trim()) params.search = search.trim();

  const query = useQuery({
    queryKey: [...queryKey, params],
    queryFn: () => fetcher(params),
    placeholderData: (prev) => prev,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleter!(id),
    onSuccess: () => {
      toast.success('Deleted.');
      queryClient.invalidateQueries({ queryKey });
    },
    onError: (err) => toast.error(extractErrorMessage(err, 'Could not delete.')),
  });

  return {
    page, setPage,
    search, setSearch,
    pageSize,
    data: query.data,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    refetch: () => queryClient.invalidateQueries({ queryKey }),
    deleteMutation,
  };
}
