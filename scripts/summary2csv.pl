#!/usr/bin/perl

use strict;
use warnings;
use v5.10;

my @rows = ();
my %current = ();
while(<>) {
	# Ignore blank lines.
	next if /^\s*$/;

	# Change current file when we hit a block.
	if(/^== (.*) ==$/) {
		push @rows, {%current} if $current{'filename'};
		%current = ();
		$current{'filename'} = $1;
		next;
	}

	die "No current file!" unless $current{'filename'};

	# Count line.
	die "Unable to read line: $_" unless /^(\w+): (\d+) \(([\d\.]+)%\)$/;
	my $field_name = $1;
	my $field_count = $2;
	my $field_percentage = $3;

	die "Duplicate field found for $field_name" if exists $current{$field_name}; 
	$current{$field_name} = {
		'count' => $field_count,
		'percentage' => $field_percentage,
	};
}

# Write out headers.
use Data::Dumper;
my @headers = (
	'File',
	'Total identifiers',
	'Total comparisons',
	'Total comparisons %'
);
my %field_names_unsorted = map { $_ => 1 } map { keys(%$_) } @rows;
delete $field_names_unsorted{'TOTAL'};
delete $field_names_unsorted{'filename'};
my @field_names = map { ($_, $_ . ' %') } sort keys %field_names_unsorted;

say join "\t", (@headers, map { ucfirst lc } @field_names);

for my $row (@rows) {

	my $total_count = 0;
	my $total_percentage = 0;
	my $row_text = "";

	for my $fieldname (@field_names) {
		next if substr ($fieldname, -1) eq '%';

		my $count = $row->{$fieldname}->{'count'} // 0;
		my $percentage = $row->{$fieldname}->{'percentage'} // 0;

		$total_count += $count;
		$total_percentage += $percentage;

		$row_text = $row_text . "\t$count\t$percentage"
	}

	say "$row->{'filename'}\t\t$total_count\t$total_percentage$row_text"
}
