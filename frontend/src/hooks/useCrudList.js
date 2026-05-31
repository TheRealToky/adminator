import { useState } from 'react';
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { extractErrorMessage } from '@/api/client';
export function useCrudList({ queryKey, fetcher, deleter, pageSize = 25 }) {
    const queryClient = useQueryClient();
    const { t } = useTranslation();
    const [page, setPage] = useState(1);
    const [search, setSearch] = useState('');
    const params = { page, page_size: pageSize };
    if (search.trim())
        params.search = search.trim();
    const query = useQuery({
        queryKey: [...queryKey, params],
        queryFn: () => fetcher(params),
        placeholderData: (prev) => prev,
    });
    const deleteMutation = useMutation({
        mutationFn: (id) => deleter(id),
        onSuccess: () => {
            toast.success(t('common.deleted'));
            queryClient.invalidateQueries({ queryKey });
        },
        onError: (err) => toast.error(extractErrorMessage(err, t('common.deleteFailed'))),
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
