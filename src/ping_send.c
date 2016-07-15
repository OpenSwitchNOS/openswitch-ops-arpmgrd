/* Copyright (c)
*
*Usage ping6 <target_ipv6_add>
*/
#include <arpa/inet.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <netinet/ip_icmp.h>
#include <netinet/icmp6.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>

#define DEFDATALEN  56
#define MAXICMPLEN 76
#define MAXIPLEN  60

#define PACKETSIZE  64
#if 0
char *utility_usage_str = "ping <4|6> <target_ip_add>";
#endif
struct packet
{
    struct icmphdr hdr;
    char msg[PACKETSIZE-sizeof(struct icmphdr)];
};

static int create_icmp6_socket(void)
{
    int sock;
    sock = socket(AF_INET6, SOCK_RAW, IPPROTO_ICMPV6);
    return sock;
}

/*--------------------------------------------------------------------*/
/*--- checksum - standard 1s complement checksum                   ---*/
/*--------------------------------------------------------------------*/
unsigned short checksum(void *b, int len)
{   unsigned short *buf = b;
    unsigned int sum=0;
    unsigned short result;

    for ( sum = 0; len > 1; len -= 2 )
        sum += *buf++;
    if ( len == 1 )
        sum += *(unsigned char*)buf;
    sum = (sum >> 16) + (sum & 0xFFFF);
    sum += (sum >> 16);
    result = ~sum;
    return result;
}

static int create_icmp4_socket(void)
{
    int sock;
    sock = socket(AF_INET, SOCK_RAW, IPPROTO_ICMP);
    return sock;
}
void ping4(const char *target)
{
    struct sockaddr_in pingaddr;
    struct packet pckt;
    const int val=255;
    int pingsock;
    int err = -1;
    if((pingsock = create_icmp4_socket())< 0){
        printf("can not create icmp4_socket. errno = %s",strerror(errno));
        return;
    }
    if ( setsockopt(pingsock, SOL_IP, IP_TTL, &val, sizeof(val)) != 0){
        printf("Set TTL option");
        return ;
    }

    memset(&pingaddr, 0, sizeof(struct sockaddr_in));
    pingaddr.sin_family = AF_INET;
    if((err = inet_pton(AF_INET, target, &pingaddr.sin_addr)) <= 0){
        printf("The given target_ip_add is not valid. error: %d",err);
        return ;
    }

    memset(&pckt, 0, sizeof(pckt));
    pckt.hdr.type = ICMP_ECHO;
    pckt.hdr.un.echo.id = 1234;
    pckt.hdr.un.echo.sequence = 1;
    pckt.hdr.checksum = checksum(&pckt, sizeof(pckt));

    if ( sendto(pingsock, &pckt, sizeof(pckt), 0,
                 (struct sockaddr*)&pingaddr, sizeof(pingaddr)) <= 0 ){
        printf("error:sendto: errno = %s",strerror(errno) );
        return;
    }
}

void ping6(const char *target)
{
    struct sockaddr_in6 pingaddr;
    struct icmp6_hdr *pkt;
    int pingsock, c;
    int sockopt;
    int err;
    char packet[DEFDATALEN + MAXIPLEN + MAXICMPLEN];

    if((pingsock = create_icmp6_socket())< 0){
        printf("can not create icmp6_socket. err= %d\n", pingsock);
        return;
    }
    memset(&pingaddr, 0, sizeof(struct sockaddr_in));
    pingaddr.sin6_family = AF_INET6;

    if((err = inet_pton(AF_INET6, target, &pingaddr.sin6_addr)) <= 0){
        printf("The given target_ip_add is not valid. error: %d",err);
        return ;
    }

    pkt = (struct icmp6_hdr *) packet;
    memset(pkt, 0, sizeof(packet));
    pkt->icmp6_type = ICMP6_ECHO_REQUEST;

    sockopt = 2;
    setsockopt(pingsock, SOL_RAW, IPV6_CHECKSUM, (char *) &sockopt,
               sizeof(sockopt));

    c = sendto(pingsock, packet, sizeof(packet), 0,
               (struct sockaddr *) &pingaddr, sizeof(struct sockaddr_in6));

    if (c < 0 )
        printf("error:sendto: errno = %s",strerror(errno) );
    return;
}
#if 0
int main(int argc, char **argv){
    char *str;
    argc--;
    argv++;
    if (argc < 2){
        printf("usage:%s\n", utility_usage_str);
    }
    str = *argv;
    long val = strtol(str, NULL, 10);
    argv++;
    if(val == 6)
        ping6(*argv);
    else if(val == 4)
        ping4(*argv);
    return 0;
}
#endif
